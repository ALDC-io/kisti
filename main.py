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
    parser.add_argument("--sim-ambient", action="store_true",
                        help="Run ambient weather simulation (scripted scenario, ~90s)")
    parser.add_argument("--sim-voice", action="store_true",
                        help="Simulate voice queries through full KiSTI pipeline")
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

    # Ambient weather sensor (Yoctopuce Yocto-Meteo-V2) or simulator
    ambient_source = None  # YoctopuceReader or AmbientSimulator — same signal interface
    ambient_tick = [0]

    if args.sim_ambient:
        from sensors.ambient_simulator import AmbientSimulator
        ambient_source = AmbientSimulator()
    else:
        try:
            from sensors.yoctopuce_reader import YoctopuceReader
            yocto = YoctopuceReader()
            if yocto.start():
                ambient_source = yocto
                log.info("Ambient sensor online: Yoctopuce Yocto-Meteo-V2")
            else:
                log.info("No Yoctopuce sensor found")
        except Exception as exc:
            log.info("Ambient sensor unavailable: %s", exc)

    if ambient_source:
        ambient_source.reading_updated.connect(
            lambda r: bridge.update_ambient(
                r.temperature_c, r.humidity_pct, r.pressure_hpa,
                r.density_altitude_ft, r.dew_point_c,
            )
        )

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
            db_store = None

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

    # --- Ambient condition tracking (independent of ECU session) ---
    # Wired AFTER window so queue_speech() is available via AudioPlayer
    if db_store and ambient_source:
        def _on_ambient_reading(reading):
            """Record ambient data at ~1/60 Hz (once per minute)."""
            ambient_tick[0] += 1
            if ambient_tick[0] % 60 == 0:
                try:
                    db_store.record_ambient(
                        reading.temperature_c, reading.humidity_pct,
                        reading.pressure_hpa, reading.density_altitude_ft,
                        reading.dew_point_c,
                    )
                except Exception:
                    pass

        def _on_condition_changed(change):
            """Record condition change event + announce via voice."""
            try:
                state = bridge.snapshot()
                db_store.record_ambient(
                    state.ambient_temp_c, state.ambient_humidity_pct,
                    state.ambient_pressure_hpa, state.density_altitude_ft,
                    state.dew_point_c,
                    change_event=change.event, change_delta=change.delta,
                )
            except Exception:
                pass
            window.queue_speech(change.message, urgency="alert")

        ambient_source.reading_updated.connect(_on_ambient_reading)
        ambient_source.condition_changed.connect(_on_condition_changed)
        log.info("Ambient DuckDB recording enabled (1/min + change events)")

    elif ambient_source:
        ambient_source.condition_changed.connect(
            lambda c: window.queue_speech(c.message, urgency="alert")
        )

    # --- Ambient simulation lifecycle ---
    if args.sim_ambient and ambient_source:
        from sensors.ambient_simulator import AmbientSimulator
        if isinstance(ambient_source, AmbientSimulator):
            ambient_source.simulation_started.connect(
                lambda: window.queue_speech(
                    "Starting ambient weather simulation. Monitoring conditions."
                )
            )
            ambient_source.simulation_ended.connect(
                lambda: window.queue_speech(
                    "Ambient weather simulation complete."
                )
            )
            ambient_source.simulation_started.connect(
                lambda: log.info("SIM: Ambient weather simulation started")
            )
            ambient_source.simulation_ended.connect(
                lambda: log.info("SIM: Ambient weather simulation ended")
            )

            # Auto-quit after final speech has time to play
            def _sim_done():
                from PySide6.QtCore import QTimer as _QT2
                _QT2.singleShot(8000, lambda: (
                    log.info("SIM: exiting after final speech"),
                    app.quit(),
                ))
            ambient_source.simulation_ended.connect(_sim_done)

            # Start sim after startup sequence finishes (~20s for voice lines)
            from PySide6.QtCore import QTimer as _QT
            _QT.singleShot(20000, ambient_source.start)
    # --- Route LLM responses through AudioPlayer (aplay) ---
    if voice_mgr:
        voice_mgr.response_ready.connect(
            lambda text: window.queue_speech(text)
        )

    # --- Simulated voice queries ---
    if args.sim_voice and voice_mgr:
        _SIM_QUERIES = [
            "How are conditions looking?",
            "What is the oil pressure like?",
            "Tell me about the turbo setup.",
            "Who are you?",
            "What should I watch out for today?",
            "How is the DCCD performing?",
            "Give me a systems check.",
        ]
        _sim_idx = [0]

        def _sim_next_query():
            if _sim_idx[0] < len(_SIM_QUERIES):
                q = _SIM_QUERIES[_sim_idx[0]]
                _sim_idx[0] += 1
                log.info("SIM VOICE [%d/%d]: %s", _sim_idx[0], len(_SIM_QUERIES), q)
                window.queue_speech(f"Driver says: {q}", urgency="normal")
                # Run LLM off main thread to avoid UI freeze
                import threading
                from PySide6.QtCore import QTimer as _QTV
                def _run_query():
                    import time as _t; _t.sleep(4)  # wait for "Driver says" to play
                    voice_mgr.handle_voice_query(q)
                threading.Thread(target=_run_query, daemon=True).start()
                # Schedule next query after response has time to play
                _QTV.singleShot(25000, _sim_next_query)
            else:
                log.info("SIM VOICE: All queries complete")
                window.queue_speech("Voice simulation complete.")

        # Start after startup sequence
        from PySide6.QtCore import QTimer as _QT3
        _QT3.singleShot(25000, _sim_next_query)

    window.show()

    log.info("KiSTI running — SI Drive: %s, Voice: %s, DuckDB: %s, Sync: %s, CAN Out: %s, Ambient: %s",
             mode_mgr.si_drive_mode.label,
             "ON" if voice_mgr else "OFF",
             "ON" if db_store else "OFF",
             "ON" if sync_mgr else "OFF",
             "ON" if can_output else "OFF",
             "SIM" if args.sim_ambient else ("YOCTO" if ambient_source else "OFF"))

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
    if ambient_source:
        ambient_source.stop()
    mode_mgr.stop()
    alert_eng.stop()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
