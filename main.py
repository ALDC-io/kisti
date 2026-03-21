#!/usr/bin/env python3
"""KiSTI — Edge AI Co-Driver

Visual telemetry + voice intelligence for Kenwood Excelon head unit (800x480).
Runs on Jetson Orin Nano with X11/eglfs display.

Subsystems:
  - CAN bus listener (Link G5 Neo 4 telemetry, SI Drive, keypad)
  - Voice pipeline (WhisperTRT STT → Ollama LLM → Piper TTS → USB audio)
  - Mode manager (Intelligent / Sport / Sport Sharp via SI Drive)
  - Alert engine (deterministic Tier 1 threshold monitoring)
  - DuckDB semantic layer (local session storage)
  - LED waveform output (MXG Strada dash shift lights via CAN)
  - Nextcloud sync (WiFi-based cloud sync to Zeus Memory)

Usage:
    python3 main.py                  # Windowed 800x480
    python3 main.py --fullscreen     # Fullscreen
    python3 main.py --display :0     # Specify X display
    python3 main.py --platform eglfs # Use eglfs instead of xcb
    python3 main.py --no-voice       # Disable voice pipeline
    python3 main.py --no-sync        # Disable cloud sync

Prerequisites:
    pip install PySide6 duckdb python-can sounddevice numpy
    sudo apt-get install libxcb-cursor0  # Required for xcb platform
"""

import argparse
import logging
import os
import sys


def setup_logging() -> None:
    """Configure logging for KiSTI."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def main():
    parser = argparse.ArgumentParser(description="KiSTI — Edge AI Co-Driver")
    parser.add_argument("--fullscreen", action="store_true", help="Start in fullscreen mode")
    parser.add_argument("--display", type=str, default=None, help="X11 display (e.g. :0)")
    parser.add_argument("--platform", type=str, default=None,
                        help="Qt platform plugin (xcb, eglfs, linuxfb, offscreen)")
    parser.add_argument("--no-voice", action="store_true", help="Disable voice pipeline")
    parser.add_argument("--no-sync", action="store_true", help="Disable cloud sync")
    parser.add_argument("--no-duckdb", action="store_true", help="Disable DuckDB recording")
    parser.add_argument("--demo", action="store_true", help="Enable demo mode (idle chatter)")
    args = parser.parse_args()

    setup_logging()
    log = logging.getLogger("kisti")

    if args.display:
        os.environ["DISPLAY"] = args.display

    if args.platform:
        os.environ["QT_QPA_PLATFORM"] = args.platform

    # Verify DISPLAY is set (unless using a non-X11 platform)
    non_x11 = os.environ.get("QT_QPA_PLATFORM", "") in ("eglfs", "linuxfb", "offscreen")
    if "DISPLAY" not in os.environ and not non_x11:
        print("ERROR: DISPLAY environment variable not set.")
        print("Try: export DISPLAY=:0 && python3 main.py")
        print("Or:  python3 main.py --platform eglfs")
        sys.exit(1)

    # Import Qt after environment is configured
    from PySide6.QtWidgets import QApplication

    from can.kisti_can import create_can_source, CanOutputThread
    from model.vehicle_state import DiffStateBridge
    from modes.mode_manager import ModeManager
    from alerts.alert_engine import AlertEngine
    from ui.main_window import MainWindow

    app = QApplication(sys.argv)

    # Core: CAN bus bridge
    bridge = DiffStateBridge()
    listener, mock = create_can_source(bridge)

    # Mode manager: SI Drive → subsystem control
    mode_mgr = ModeManager(bridge)
    mode_mgr.start()

    # Alert engine: deterministic Tier 1 threshold monitoring
    alert_eng = AlertEngine(bridge)
    alert_eng.start()

    # Voice pipeline (optional)
    voice_mgr = None
    if not args.no_voice:
        try:
            from voice.voice_manager import VoiceManager
            voice_mgr = VoiceManager()
            voice_mgr.start()

            # Wire mode changes to voice manager
            mode_mgr.si_drive_changed.connect(
                lambda m: voice_mgr.set_si_drive_mode(
                    __import__("model.vehicle_state", fromlist=["SIDriveMode"]).SIDriveMode(m)
                )
            )
            mode_mgr.voice_toggle.connect(voice_mgr.toggle_voice)

            # Wire alerts to voice
            alert_eng.alert_fired.connect(
                lambda a: voice_mgr.speak_alert(a.message, a.severity.label)
            )

            # Wire analyze run (K3) to voice query
            mode_mgr.analyze_run.connect(
                lambda: voice_mgr.handle_voice_query("Analyze that run")
            )

            log.info("Voice pipeline enabled")
        except Exception as exc:
            log.warning("Voice pipeline failed to start: %s", exc)

    # DuckDB session recording (optional)
    db_store = None
    if not args.no_duckdb:
        try:
            from data.duckdb_store import DuckDBStore
            db_store = DuckDBStore()
            db_store.open()
            log.info("DuckDB session store ready")
        except Exception as exc:
            log.warning("DuckDB failed to initialize: %s", exc)

    # Cloud sync (optional)
    sync_mgr = None
    if not args.no_sync and db_store is not None:
        try:
            from sync.sync_manager import SyncManager
            sync_mgr = SyncManager(db_store=db_store)
            sync_mgr.start()

            # Announce sync completion via voice
            if voice_mgr:
                sync_mgr.sync_complete.connect(
                    lambda n: voice_mgr.speak(f"Session upload complete. {n} session{'s' if n > 1 else ''} synced.")
                )

            log.info("Cloud sync enabled")
        except Exception as exc:
            log.warning("Cloud sync failed to start: %s", exc)

    # Start CAN source — real hardware only, no mock
    can_output = None
    if listener:
        listener.start()
        log.info("CAN listener started")

        # LED output to AiM MXG Strada shift lights via CAN
        can_output = CanOutputThread()
        can_output.start()
        log.info("CAN LED output started (30 Hz → 0x6C0/0x6C1)")

        # Wire voice LED frames to CAN output
        if voice_mgr:
            voice_mgr.led_frame_ready.connect(
                lambda f: can_output.set_leds(
                    f.mode, f.brightnesses, f.color_r, f.color_g, f.color_b
                )
            )
    else:
        log.info("No CAN hardware — ECU features disabled")

    # --- DuckDB session lifecycle (K1 start/stop, telemetry recording) ---
    session_id = None
    telemetry_tick = [0]  # mutable for closure

    if db_store:
        def _on_state_changed():
            telemetry_tick[0] += 1
            # Record telemetry at ~1 Hz (bridge fires at 20-50 Hz)
            if session_id and telemetry_tick[0] % 20 == 0:
                try:
                    db_store.record_telemetry(session_id, bridge.snapshot())
                except Exception:
                    pass
            # Feed voice telemetry context every ~5s
            if voice_mgr and telemetry_tick[0] % 100 == 0:
                voice_mgr.set_telemetry(bridge.snapshot())

        def _on_session_toggle():
            nonlocal session_id
            if session_id is None:
                session_id = db_store.start_session(
                    si_drive_mode=mode_mgr.si_drive_mode.label,
                )
                if voice_mgr:
                    voice_mgr.speak("Session recording started.")
                log.info("Session started: %s", session_id[:8])
            else:
                db_store.end_session(session_id)
                if voice_mgr:
                    voice_mgr.speak("Session recording stopped.")
                log.info("Session ended: %s", session_id[:8])
                session_id = None

        bridge.state_changed.connect(_on_state_changed)
        mode_mgr.session_toggle.connect(_on_session_toggle)

        # Record alerts to DuckDB
        alert_eng.alert_fired.connect(
            lambda a: db_store.record_alert(
                session_id or "no-session",
                a.alert_type, a.severity.label, a.message, a.value,
            )
        )
        log.info("DuckDB session lifecycle wired (K1 start/stop)")

    # UI — pass the shared bridge so CAN data flows to display
    window = MainWindow(fullscreen=args.fullscreen, bridge=bridge)
    window.show()

    log.info("KiSTI running — SI Drive: %s, Voice: %s, DuckDB: %s, Sync: %s, CAN Out: %s",
             mode_mgr.si_drive_mode.label,
             "ON" if voice_mgr else "OFF",
             "ON" if db_store else "OFF",
             "ON" if sync_mgr else "OFF",
             "ON" if can_output else "OFF")

    # Run Qt event loop
    exit_code = app.exec()

    # Cleanup
    log.info("Shutting down...")
    if listener:
        listener.stop()
    if can_output:
        can_output.stop()
    if mock:
        mock.stop()
    if voice_mgr:
        voice_mgr.stop()
    if sync_mgr:
        sync_mgr.stop()
    if db_store:
        if session_id:
            db_store.end_session(session_id)
        db_store.close()
    mode_mgr.stop()
    alert_eng.stop()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
