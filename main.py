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
    parser.add_argument("--no-memory", action="store_true", help="Disable edge memory system")
    parser.add_argument("--no-zeus-sync", action="store_true", help="Disable Zeus memory sync")
    parser.add_argument("--demo", action="store_true",
                        help="Trade show mode: mock CAN telemetry + SI-Drive rotation")
    parser.add_argument("--sim-ambient", action="store_true",
                        help="Run ambient weather simulation (scripted scenario, ~90s)")
    parser.add_argument("--sim-voice", action="store_true",
                        help="Simulate voice queries through full KiSTI pipeline")
    parser.add_argument("--no-mic", action="store_true",
                        help="Disable microphone capture (no voice input)")
    parser.add_argument("--mic-device", type=str, default="default",
                        help="ALSA capture device for mic (default: 'default')")
    parser.add_argument("--headless", action="store_true",
                        help="Headless voice mode — no display, pure voice chat")
    args = parser.parse_args()

    setup_logging()
    log = logging.getLogger("kisti")

    # HDMI audio: PulseAudio must stay running to keep the HDA pin-ctl
    # active (Jetson Orin Nano resets pin to 0x00 when PA exits).
    # kisti-session handles PA startup. If PA isn't running (e.g. dev mode),
    # start it here. Must unset PULSE_SERVER to avoid "refusing to start" error.
    import subprocess as _sp
    _pa_check = _sp.run(["pulseaudio", "--check"], capture_output=True)
    if _pa_check.returncode != 0:
        log.info("PulseAudio not running — starting for HDMI audio...")
        import os as _os
        _env = _os.environ.copy()
        _env.pop("PULSE_SERVER", None)
        _sp.run(["pulseaudio", "--start", "--exit-idle-time=-1"], capture_output=True, env=_env)
        import time as _time
        _time.sleep(2)
    _pa_ok = _sp.run(["pulseaudio", "--check"], capture_output=True)
    if _pa_ok.returncode == 0:
        # Prefer USB speaker if connected, otherwise HDMI
        _usb_check = _sp.run(["pactl", "list", "sinks", "short"], capture_output=True, text=True)
        _usb_sink = ""
        for _line in _usb_check.stdout.splitlines():
            if "usb" in _line.lower() and "monitor" not in _line.lower():
                _usb_sink = _line.split()[1]
                break
        if _usb_sink:
            _sp.run(["pactl", "set-default-sink", _usb_sink], capture_output=True)
            _sp.run(["pactl", "set-sink-volume", _usb_sink, "78%"], capture_output=True)
            log.info("Audio: USB speaker default — %s @ 78%%", _usb_sink)
        else:
            _sp.run(["pactl", "set-default-sink",
                     "alsa_output.platform-3510000.hda.HiFi__hw_HDA_3__sink"],
                    capture_output=True)
            log.info("Audio: HDMI sink default — no USB speaker found")
    else:
        log.warning("HDMI audio: PulseAudio not running — audio will not work")

    if args.headless:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
    else:
        if args.display:
            os.environ["DISPLAY"] = args.display
        if args.platform:
            os.environ["QT_QPA_PLATFORM"] = args.platform
        # Verify DISPLAY is set (unless using a non-X11 platform)
        non_x11 = os.environ.get("QT_QPA_PLATFORM", "") in ("eglfs", "linuxfb", "offscreen")
        if "DISPLAY" not in os.environ and not non_x11:
            print("ERROR: DISPLAY environment variable not set.")
            print("Try: export DISPLAY=:0 && python3 main.py")
            print("Or:  python3 main.py --headless")
            sys.exit(1)

    # Graceful shutdown on SIGTERM/SIGINT (systemd sends SIGTERM on stop)
    import signal
    _original_sigterm = signal.getsignal(signal.SIGTERM)
    _original_sigint = signal.getsignal(signal.SIGINT)

    # Import Qt after environment is configured
    from can.kisti_can import create_can_source, CanOutputThread
    from model.vehicle_state import DiffStateBridge
    from modes.mode_manager import ModeManager
    from alerts.alert_engine import AlertEngine

    if args.headless:
        from PySide6.QtCore import QCoreApplication
        app = QCoreApplication(sys.argv)
        log.info("Headless voice mode — no display")
    else:
        from PySide6.QtWidgets import QApplication
        from ui.main_window import MainWindow
        app = QApplication(sys.argv)

    # Wire signal handlers now that QApplication exists
    signal.signal(signal.SIGTERM, lambda *_: app.quit())
    signal.signal(signal.SIGINT, lambda *_: app.quit())

    # Core: CAN bus bridge
    bridge = DiffStateBridge()

    # SIGUSR1: cycle SI Drive mode (for dev/demo without CAN hardware)
    _usr1_mode = [0]  # mutable counter: 0=I, 1=S, 2=S#

    def _cycle_si_drive(*_args):
        _usr1_mode[0] = (_usr1_mode[0] + 1) % 3
        bridge.update_si_drive(_usr1_mode[0])
        log.info("SIGUSR1 → SI Drive mode %d", _usr1_mode[0])

    signal.signal(signal.SIGUSR1, _cycle_si_drive)
    listener, mock = create_can_source(bridge)
    # Demo mode: start mock CAN with SI-Drive cycling for trade shows
    if args.demo and mock is not None:
        mock.set_demo_mode(True)
        mock.start()
        log.info("Demo mode: mock CAN active, SI-Drive cycling I→S→S# every 15s")

    # Mode manager: SI Drive → subsystem control
    mode_mgr = ModeManager(bridge)
    mode_mgr.start()

    # Alert engine: deterministic Tier 1 threshold monitoring
    alert_eng = AlertEngine(bridge)
    alert_eng.start()
    mode_mgr.si_drive_changed.connect(alert_eng.set_si_drive_mode)

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

    # Weather nowcasting engine — feeds trend data into DiffState
    from sensors.weather_engine import WeatherEngine
    weather_engine = WeatherEngine()

    # Environment Canada regional weather (extends prediction window)
    ec_poller = None
    try:
        from sensors.ec_weather import ECWeatherPoller
        ec_poller = ECWeatherPoller()
        ec_poller.start()
    except Exception as exc:
        log.info("EC weather poller unavailable: %s", exc)

    if ambient_source:
        def _on_ambient_for_bridge_and_weather(r):
            bridge.update_ambient(
                r.temperature_c, r.humidity_pct, r.pressure_hpa,
                r.density_altitude_ft, r.dew_point_c,
            )
            # Fuse hyperlocal sensors with EC regional data
            import time as _wtime
            ec_level = "none"
            ec_age = 9999.0
            if ec_poller:
                ec = ec_poller.data
                if ec.available:
                    ec_level = ec.highest_warning
                    ec_age = (_wtime.monotonic() - ec.fetch_ts) if ec.fetch_ts else 9999.0
                    bridge.update_ec_weather(
                        ec.highest_warning, ec.warning_text,
                        ec.ec_condition, ec.forecast_condition, ec_age,
                        warning_description=ec.warning_description,
                    )
            wx = weather_engine.feed(
                r.pressure_hpa, r.humidity_pct,
                r.temperature_c, r.dew_point_c,
                ec_warning_level=ec_level,
                ec_data_age_s=ec_age,
            )
            bridge.update_weather_trends(
                wx.pressure_trend_hpa_hr, wx.humidity_trend_pct_hr,
                wx.dew_point_spread_c, wx.threat_label,
            )

        ambient_source.reading_updated.connect(_on_ambient_for_bridge_and_weather)

    # FLIR Lepton thermal camera (road surface temps — forward-facing)
    flir_reader = None
    try:
        from sensors.flir_lepton_reader import FLIRLeptonReader
        flir_reader = FLIRLeptonReader()
        if flir_reader.start():
            flir_reader.temps_updated.connect(
                lambda t: bridge.update_road_surface(t.left, t.center, t.right)
            )
            log.info("FLIR Lepton online: road surface thermal imaging")
        else:
            log.info("No FLIR Lepton found — road surface temps unavailable")
            flir_reader = None
    except Exception as exc:
        log.info("FLIR Lepton unavailable: %s", exc)
        flir_reader = None

    # Voice pipeline (optional)
    voice_mgr = None
    if not args.no_voice:
        try:
            from voice.voice_manager import VoiceManager
            voice_mgr = VoiceManager(
                mic_device=args.mic_device,
                enable_mic=not args.no_mic,
            )
            voice_mgr.start()

            # Wire mode changes to voice manager + personality quotes
            from model.vehicle_state import SIDriveMode
            from data.event_quotes import get_alert_quote, get_event_quote_with_chance

            def _on_mode_change(m):
                mode = SIDriveMode(m)
                voice_mgr.set_si_drive_mode(mode)
                quote = get_event_quote_with_chance(f"mode_{mode.name.lower()}", chance=0.5)
                if quote:
                    voice_mgr.speak(quote)

            mode_mgr.si_drive_changed.connect(_on_mode_change)
            mode_mgr.voice_toggle.connect(voice_mgr.toggle_voice)

            # Wire alerts to voice + personality quotes.
            # grip_low_grip → voice (safety-critical, RWR/TCAS principle).
            # grip_wet, grip_cold, grip_cleared → visual only (no voice chatter).
            _VISUAL_ONLY_TYPES = frozenset({
                "grip_wet", "grip_cold", "grip_cleared",
            })

            def _on_alert(a):
                if a.alert_type in _VISUAL_ONLY_TYPES:
                    return  # visual-only — no voice, no quote
                # Safety-critical types spoken via voice_alert signal
                if a.alert_type not in AlertEngine.VOICE_ALERT_TYPES:
                    voice_mgr.speak_alert(a.message, a.severity.label)
                quote = get_alert_quote(a.alert_type)
                if quote:
                    voice_mgr.speak(quote)

            alert_eng.alert_fired.connect(_on_alert)

            # Safety-critical alerts → dedicated voice routing
            # voice_alert is gated by VOICE_ALERT_TYPES — always speak, all modes
            alert_eng.voice_alert.connect(
                lambda a: voice_mgr.speak_alert(a.message, "critical")
            )

            # Wire analyze run (K3) to voice query
            mode_mgr.analyze_run.connect(
                lambda: voice_mgr.handle_voice_query("Analyze that run")
            )

            # Wire keypad buttons to voice control
            # Voice toggle: K4 via mode_manager.voice_toggle signal (line 200)
            # Push-to-talk: K2 handled here (hold to listen without wake word)
            ptt_state = [False]  # track K2 state for release detection

            def _on_keypad_pressed(button_mask: int):
                """Handle keypad button presses for push-to-talk (K2)."""
                if button_mask & 0x02:
                    # K2: Push-to-talk — enable passthrough
                    if voice_mgr._mic:
                        voice_mgr._mic.set_passthrough(True)
                        ptt_state[0] = True
                        log.info("K2: push-to-talk started (passthrough enabled)")

            def _check_keypad_release():
                """Check for K2 release and disable passthrough."""
                if ptt_state[0]:
                    snap = bridge.snapshot()
                    if not (snap.keypad_state & 0x02):
                        # K2 released
                        if voice_mgr._mic:
                            voice_mgr._mic.set_passthrough(False)
                            ptt_state[0] = False
                            log.info("K2: push-to-talk ended (passthrough disabled)")

            bridge.keypad_pressed.connect(_on_keypad_pressed)
            bridge.state_changed.connect(_check_keypad_release)

            log.info("Voice pipeline enabled")

            # Feed ambient sensor data to voice manager for weather queries.
            # CAN telemetry callback (line 490) handles this when CAN is live,
            # but without CAN hardware, voice_mgr never gets ambient updates.
            if ambient_source:
                _voice_ambient_tick = [0]

                def _feed_voice_ambient(reading):
                    _voice_ambient_tick[0] += 1
                    if _voice_ambient_tick[0] % 5 == 0:  # ~every 5s
                        voice_mgr.set_telemetry(bridge.snapshot())

                ambient_source.reading_updated.connect(_feed_voice_ambient)
                log.info("Ambient → voice telemetry feed enabled")

        except Exception as exc:
            log.warning("Voice pipeline failed to start: %s", exc)

    # Warm object detection — display only, no voice (too many false positives stationary)
    if flir_reader is not None:
        log.info("Warm object detection enabled (display only, no voice)")

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

    # Edge memory system (optional, requires DuckDB)
    edge_memory = None
    embedder = None
    if not args.no_memory and db_store is not None:
        try:
            from data.edge_embedder import EdgeEmbedder
            from data.edge_memory import EdgeMemory

            embedder = EdgeEmbedder()
            if embedder.start():
                log.info("ONNX embedder ready: all-MiniLM-L6-v2 INT8 (384-dim)")
            else:
                log.info("ONNX embedder unavailable — memory search uses keyword fallback")
                embedder = None

            edge_memory = EdgeMemory(db_store=db_store, embedder=embedder)
            edge_memory.initialize()
            log.info("Edge memory system ready")
        except Exception as exc:
            log.warning("Edge memory failed to initialize: %s", exc)
            edge_memory = None

    # Zeus memory sync (optional, requires edge_memory)
    zeus_sync = None
    if not args.no_zeus_sync and edge_memory is not None:
        try:
            from sync.zeus_memory_sync import ZeusMemorySyncWorker
            api_key = os.environ.get("ZEUS_API_KEY", "")
            if api_key:
                zeus_sync = ZeusMemorySyncWorker(edge_memory=edge_memory, api_key=api_key)
                zeus_sync.start()

                if voice_mgr:
                    zeus_sync.sync_complete.connect(
                        lambda n: voice_mgr.speak(
                            f"Memory sync complete. {n} memor{'ies' if n > 1 else 'y'} uploaded."
                        )
                    )

                log.info("Zeus memory sync enabled")
            else:
                log.info("ZEUS_API_KEY not set — Zeus memory sync disabled")
        except Exception as exc:
            log.warning("Zeus memory sync failed to start: %s", exc)

    # Inject edge memory into voice pipeline
    if voice_mgr and edge_memory:
        voice_mgr.set_edge_memory(edge_memory)
        log.info("Voice 'remember' commands + memory context enabled")

    # Inject DuckDB into voice pipeline for latency recording
    if voice_mgr and db_store:
        voice_mgr.set_duckdb_store(db_store)
        log.info("Voice latency recording enabled")

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

    # Race analysis timing (optional — requires DuckDB for track database)
    timing_mgr = None
    if db_store is not None:
        try:
            from timing.timing_manager import TimingManager
            timing_mgr = TimingManager(bridge=bridge, db_store=db_store)
            timing_mgr.start()

            # Voice announcements for timing events (mode-aware)
            if voice_mgr:
                voice_mgr.set_timing_manager(timing_mgr)

                def _on_lap_complete(e):
                    mode = mode_mgr.si_drive_mode
                    lap = e["lap_number"]
                    t = e["time_s"]
                    delta = e["delta_s"]
                    tb = e.get("theoretical_best_s")
                    trend = _session_lap_tracker.complete_lap(lap, t) if _session_lap_tracker else ""

                    if mode == SIDriveMode.SPORT_SHARP:
                        # S# — PBs only (new best lap)
                        if delta < 0:
                            msg = f"P B. {t:.1f}."
                            if trend:
                                msg += f" {trend}"
                            voice_mgr.speak(msg)
                    elif mode == SIDriveMode.SPORT:
                        # S — lap + delta + trend
                        msg = f"{t:.1f}."
                        if delta != 0:
                            d = "plus" if delta > 0 else "minus"
                            msg += f" {d} {abs(delta):.1f}."
                        if trend:
                            msg += f" {trend}"
                        voice_mgr.speak(msg)
                    else:
                        # I — full detail + trend
                        msg = f"Lap {lap}: {t:.1f} seconds."
                        if delta != 0:
                            d = "plus" if delta > 0 else "minus"
                            msg += f" {d} {abs(delta):.1f}."
                        if tb and tb > 0:
                            msg += f" Theoretical best: {tb:.1f}."
                        if trend:
                            msg += f" {trend}"
                        voice_mgr.speak(msg)

                timing_mgr.lap_completed.connect(_on_lap_complete)

                def _on_track_detected(name):
                    mode = mode_mgr.si_drive_mode
                    if mode != SIDriveMode.SPORT_SHARP:
                        voice_mgr.speak(f"Track detected: {name}.")

                timing_mgr.track_detected.connect(_on_track_detected)

                def _on_sector_complete(e):
                    mode = mode_mgr.si_drive_mode
                    if mode == SIDriveMode.SPORT_SHARP:
                        return  # S# — silent on sectors
                    t = e["time_s"]
                    idx = e["sector_index"] + 1  # 1-based for speech
                    if mode == SIDriveMode.SPORT:
                        voice_mgr.speak(f"S{idx}: {t:.1f}.")
                    else:
                        # Intelligent — sector time + cumulative split
                        splits = e.get("split_times", [])
                        cumulative = sum(splits) if splits else t
                        voice_mgr.speak(
                            f"Sector {idx}: {t:.1f}. Split {cumulative:.1f}."
                        )

                timing_mgr.sector_completed.connect(_on_sector_complete)

            log.info("Timing manager enabled")
        except Exception as exc:
            log.warning("Timing manager failed to start: %s", exc)

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

    # --- Zeus Memory timing push (fire-and-forget) ---
    def _push_timing_to_zeus(sid: str, summary: dict) -> None:
        """Push session timing summary to Zeus Memory in a background thread."""
        if not summary or summary.get("total_laps", 0) == 0:
            return
        import threading
        import json
        import urllib.request

        def _push():
            try:
                api_key = os.environ.get("ZEUS_API_KEY", "")
                if not api_key:
                    log.debug("No ZEUS_API_KEY — skipping timing push")
                    return
                payload = json.dumps({
                    "content": (
                        f"KiSTI timing session {sid[:8]}: "
                        f"{summary['total_laps']} laps at {summary.get('track_name', 'Unknown')}. "
                        f"Best: lap {summary['best_lap_number']} @ {summary['best_lap_time_s']:.1f}s. "
                        f"Theoretical: {summary.get('theoretical_best_s', 0):.1f}s."
                    ),
                    "source": "kisti_timing",
                    "metadata": {
                        "type": "timing_session",
                        "session_id": sid,
                        "track_name": summary.get("track_name", "Unknown"),
                        "total_laps": summary["total_laps"],
                        "best_lap_time_s": summary["best_lap_time_s"],
                        "best_lap_number": summary["best_lap_number"],
                        "theoretical_best_s": summary.get("theoretical_best_s"),
                        "last_lap_time_s": summary.get("last_lap_time_s"),
                    },
                }).encode("utf-8")
                req = urllib.request.Request(
                    "https://zeus.aldc.io/api/memory",
                    data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "X-API-Key": api_key,
                    },
                    method="POST",
                )
                urllib.request.urlopen(req, timeout=5)
                log.info("Timing summary pushed to Zeus Memory")
            except Exception as exc:
                log.debug("Zeus timing push failed (non-critical): %s", exc)

        threading.Thread(target=_push, daemon=True).start()

    # --- DuckDB session lifecycle + data collection ---
    session_id = None
    telemetry_tick = [0]  # mutable for closure
    _telemetry_buffer = []  # batch buffer for native-rate telemetry
    _prev_knock_count = [0]  # track knock count changes
    pattern_eng = None
    parked_debrief = None
    _pending_debrief = [None]  # debrief text from bg thread → UI coaching bar

    if db_store:
        # Pattern engine: 1Hz CPU-only analysis
        from analysis.pattern_engine import PatternEngine
        pattern_eng = PatternEngine(db_store, lambda: session_id)

        # Parked debrief: Haiku session analysis (WiFi-gated)
        from analysis.parked_debrief import ParkedDebrief
        _anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
        parked_debrief = ParkedDebrief(db_store, _anthropic_key) if _anthropic_key else None

        def _on_state_changed():
            telemetry_tick[0] += 1
            if not session_id:
                # Feed voice telemetry context every ~5s even without session
                if voice_mgr and telemetry_tick[0] % 100 == 0:
                    voice_mgr.set_telemetry(bridge.snapshot())
                return

            # Buffer telemetry at native rate (bridge fires at 20-50 Hz)
            try:
                snap = bridge.snapshot()
                _telemetry_buffer.append(snap)

                # Flush buffer every ~1 second (every 50 ticks at 50Hz)
                if telemetry_tick[0] % 50 == 0 and _telemetry_buffer:
                    for s in _telemetry_buffer:
                        db_store.record_telemetry(session_id, s)
                    _telemetry_buffer.clear()

                # Track knock count changes for knock_events table
                # (knock_count and iam come from Link G5 CAN when configured)
                knock = getattr(snap, 'knock_count', None)
                if knock is not None and knock > _prev_knock_count[0]:
                    delta = knock - _prev_knock_count[0]
                    boost_psi = (getattr(snap, 'map_kpa', 0) or 0) * 0.14503773 - 14.696
                    db_store.record_knock_event(
                        session_id, delta,
                        rpm=snap.rpm or 0,
                        boost_psi=max(0, boost_psi),
                        gear=snap.gear or 0,
                        iam=getattr(snap, 'iam', 1.0) or 1.0,
                    )
                if knock is not None:
                    _prev_knock_count[0] = knock

            except Exception:
                pass

            # Feed voice telemetry context every ~5s
            if voice_mgr and telemetry_tick[0] % 100 == 0:
                voice_mgr.set_telemetry(bridge.snapshot())

        def _on_flir_temps(temps):
            """Log FLIR road temps to DuckDB at 3Hz."""
            if session_id:
                try:
                    snap = bridge.snapshot()
                    db_store.record_flir_temps(
                        session_id, temps.left, temps.center, temps.right,
                        snap.surface_state.label,
                    )
                except Exception:
                    pass

        def _on_surface_state_changed(from_state: str, to_state: str):
            """Log surface state transitions to DuckDB."""
            if session_id:
                try:
                    snap = bridge.snapshot()
                    db_store.record_surface_transition(
                        session_id, from_state, to_state,
                        snap.road_temp_center or 0.0,
                        snap.dew_point_c or 0.0,
                    )
                except Exception:
                    pass

        def _on_session_toggle():
            nonlocal session_id
            if session_id is None:
                session_id = db_store.start_session(
                    si_drive_mode=mode_mgr.si_drive_mode.label,
                )
                _prev_knock_count[0] = 0
                _telemetry_buffer.clear()
                if timing_mgr:
                    timing_mgr.set_session_id(session_id)
                if pattern_eng:
                    pattern_eng.start()
                if voice_mgr:
                    voice_mgr.speak("Session recording started.")
                log.info("Session started: %s", session_id[:8])
            else:
                # Flush remaining telemetry buffer
                if _telemetry_buffer:
                    for s in _telemetry_buffer:
                        try:
                            db_store.record_telemetry(session_id, s)
                        except Exception:
                            pass
                    _telemetry_buffer.clear()
                # Mode-aware timing debrief before ending session
                if timing_mgr and voice_mgr:
                    summary = timing_mgr.get_session_summary()
                    if summary.get("total_laps", 0) > 0:
                        mode = mode_mgr.si_drive_mode
                        n = summary["total_laps"]
                        best_t = summary["best_lap_time_s"]
                        best_n = summary["best_lap_number"]
                        tb = summary.get("theoretical_best_s")
                        track = summary.get("track_name", "Unknown")

                        if mode == SIDriveMode.SPORT_SHARP:
                            voice_mgr.speak(f"Done. Best: {best_t:.1f}.")
                        elif mode == SIDriveMode.SPORT:
                            voice_mgr.speak(
                                f"{n} laps. Best: {best_t:.1f}, lap {best_n}."
                            )
                        else:
                            msg = (
                                f"Session complete at {track}. "
                                f"{n} laps. Best: lap {best_n}, {best_t:.1f} seconds."
                            )
                            if tb and tb > 0:
                                msg += f" Theoretical best: {tb:.1f}."
                            last_t = summary.get("last_lap_time_s")
                            if last_t:
                                msg += f" Last lap: {last_t:.1f}."
                            voice_mgr.speak(msg)
                # Push timing summary to Zeus Memory (async, non-blocking)
                if timing_mgr:
                    _push_timing_to_zeus(session_id, timing_mgr.get_session_summary())
                    timing_mgr.set_session_id(None)
                # Stop pattern engine
                if pattern_eng:
                    pattern_eng.stop()
                db_store.end_session(session_id)
                # Trigger Haiku debrief in background if WiFi available
                if parked_debrief:
                    import threading as _debrief_threading
                    _debrief_sid = session_id
                    def _run_debrief(sid=_debrief_sid):
                        try:
                            from sync.sync_manager import SyncManager
                            if SyncManager._check_connectivity():
                                result = parked_debrief.generate(sid)
                                if result:
                                    insights = result.get("insights", "")
                                    if insights:
                                        # Push to UI coaching bar (main thread picks up)
                                        _pending_debrief[0] = insights
                                        # Speak all insights with pauses
                                        if voice_mgr:
                                            import re
                                            import time as _dtime
                                            points = re.split(r'\d+[\.\)]\s+', insights.strip())
                                            points = [p.strip() for p in points if len(p.strip()) > 10]
                                            if not points:
                                                points = [insights]
                                            voice_mgr.speak("Session debrief.")
                                            for p in points[:3]:
                                                _dtime.sleep(3)
                                                voice_mgr.speak(p)
                            else:
                                log.info("No WiFi — debrief skipped")
                        except Exception as exc:
                            log.debug("Debrief failed: %s", exc)
                    _debrief_threading.Thread(target=_run_debrief, daemon=True).start()
                if voice_mgr:
                    voice_mgr.speak("Session recording stopped.")
                log.info("Session ended: %s", session_id[:8])
                session_id = None

        bridge.state_changed.connect(_on_state_changed)
        bridge.surface_state_changed.connect(_on_surface_state_changed)
        mode_mgr.session_toggle.connect(_on_session_toggle)

        # Wire FLIR temps to DuckDB (3Hz logging)
        if flir_reader:
            flir_reader.temps_updated.connect(_on_flir_temps)
            log.info("FLIR → DuckDB wired (3Hz road temps)")

        # Record alerts to DuckDB
        alert_eng.alert_fired.connect(
            lambda a: db_store.record_alert(
                session_id or "no-session",
                a.alert_type, a.severity.label, a.message, a.value,
            )
        )
        log.info("DuckDB data collection wired (native-rate telemetry, FLIR 3Hz, surface transitions, knock events)")

        # Connect pattern → voice for safety-critical patterns
        if voice_mgr:
            def _on_pattern(p):
                if p.pattern_type == "ice_risk_imminent":
                    voice_mgr.speak_alert(
                        "Reduce speed. Ice risk.",
                        "critical",
                    )
                elif p.pattern_type == "ice_risk_trending":
                    voice_mgr.speak_alert(
                        f"Caution, road cooling toward dew point. "
                        f"Delta {p.value:.1f} degrees.",
                        "warning",
                    )
                elif p.pattern_type == "knock_burst":
                    voice_mgr.speak_alert(
                        f"Knock burst. {int(p.value)} events at "
                        f"{p.context.get('avg_rpm', 0):.0f} RPM.",
                        "warning",
                    )
            pattern_eng.pattern_detected.connect(_on_pattern)

        log.info("Pattern engine wired (1Hz analysis, session-gated)")
        if parked_debrief:
            log.info("Parked debrief enabled (Haiku, WiFi-gated)")

    # --- UI vs Headless ---
    window = None
    if not args.headless:
        window = MainWindow(
            fullscreen=args.fullscreen,
            bridge=bridge,
            mode_manager=mode_mgr,
            flir_reader=flir_reader,
        )

        # Feed DiffState snapshots to the active screen at 20Hz
        _ui_tick = [0]

        def _update_screen():
            _ui_tick[0] += 1
            snap = bridge.snapshot()
            window.update_from_bridge(snap)
            # Also feed timing display at 4Hz
            if timing_mgr and _ui_tick[0] % 5 == 0:
                if hasattr(window, '_track_mode'):
                    window._track_mode.update_timing(snap)
                # Feed timing data to Sport Sharp screen
                if hasattr(window, '_sharp_screen') and hasattr(timing_mgr, 'get_timing_data'):
                    window._sharp_screen.update_timing(timing_mgr.get_timing_data())

        bridge.state_changed.connect(_update_screen)

        # Visual flash overlay for WARNING/CRITICAL alerts in S# mode
        alert_eng.alert_fired.connect(window.flash_alert)

        if timing_mgr and mode_mgr:
            mode_mgr.si_drive_changed.connect(
                lambda m: window._track_mode.set_timing_mode(m)
                if hasattr(window, '_track_mode') else None
            )

        # --- Voice activity ticker (all 3 screens) ---
        from PySide6.QtCore import QTimer
        from collections import deque as _deque
        _voice_ticker_deque = _deque(maxlen=3)

        if voice_mgr:
            def _on_speaking_text(text: str):
                _voice_ticker_deque.appendleft(text)
            voice_mgr.speaking_text.connect(_on_speaking_text)

        _ticker_timer = QTimer()
        _ticker_timer.setInterval(1000)

        def _push_ticker():
            lines = list(_voice_ticker_deque)
            for screen in (window._intelligent_screen, window._sport_screen,
                           window._sharp_screen):
                screen.update_voice_ticker(lines)

        _ticker_timer.timeout.connect(_push_ticker)
        _ticker_timer.start()

        # --- Coaching analyzers (Sport + Sharp screen at 1Hz) ---
        from coaching.technique_analyzer import TechniqueAnalyzer
        from coaching.balance_analyzer import BalanceAnalyzer
        from coaching.grip_analyzer import GripAnalyzer
        from coaching.condition_rules import evaluate as _eval_conditions
        from coaching.session_lap_tracker import SessionLapTracker as _SessionLapTracker
        _technique_analyzer = TechniqueAnalyzer()
        _balance_analyzer = BalanceAnalyzer()
        _grip_analyzer = GripAnalyzer()
        _session_lap_tracker = _SessionLapTracker()

        _coaching_timer = QTimer()
        _coaching_timer.setInterval(1000)

        def _coaching_tick():
            snap = bridge.snapshot()

            # Technique analyzer — brake G, trail brake, coaching text
            _technique_analyzer.feed(snap)
            text, sentiment = _technique_analyzer.analyze()
            # SC-3: safety conditions override technique coaching on Sport screen
            cond = _eval_conditions(snap, 0)  # level 0 = ICE + LOW_GRIP only
            if cond:
                text, sentiment = cond
            window._sport_screen.update_coaching(text, sentiment)
            _session_lap_tracker.record_tick(text, sentiment)

            # Balance analyzer — understeer/oversteer via bicycle model
            _balance_analyzer.feed(snap)
            ratio = _balance_analyzer.current_ratio()
            bal_text, bal_sentiment = _balance_analyzer.coaching_text()
            window._sport_screen.update_balance(ratio, bal_text, bal_sentiment)
            window._sharp_screen.update_balance(ratio, bal_text, bal_sentiment)

            # Grip analyzer — per-axle traction from wheel speeds
            _grip_analyzer.feed(snap)
            front = _grip_analyzer.front_grip_pct()
            rear = _grip_analyzer.rear_grip_pct()
            window._sport_screen.update_grip(front, rear)
            window._sharp_screen.update_grip(front, rear)

            # Brake analysis — longitudinal G as peak brake G to Sport screen
            peak_g = abs(snap.imu_accel_x) if snap.imu_accel_x < -0.1 else 0.0
            trail = 1.0 if (snap.imu_accel_x < -0.3 and abs(snap.imu_accel_y) > 0.3) else 0.0
            window._sport_screen.update_brake_analysis(peak_g, trail * 100.0)

        _coaching_timer.timeout.connect(_coaching_tick)
        _coaching_timer.start()

        # --- Condition rules (Intelligent screen coaching at 1Hz) ---
        # Debrief display state (bg thread writes _pending_debrief, this timer reads)
        _debrief_items = []
        _debrief_idx = [0]
        _debrief_ticks = [0]

        _condition_timer = QTimer()
        _condition_timer.setInterval(1000)

        def _condition_tick():
            snap = bridge.snapshot()

            # Check for new debrief from background thread
            if _pending_debrief[0] is not None:
                import re
                raw = _pending_debrief[0]
                _pending_debrief[0] = None
                pts = re.split(r'\d+[\.\)]\s+', raw.strip())
                _debrief_items.clear()
                _debrief_items.extend([p.strip() for p in pts if len(p.strip()) > 10])
                _debrief_idx[0] = 0
                _debrief_ticks[0] = 0

            # Cycle debrief insights (5s each, then resume normal coaching)
            if _debrief_items:
                _debrief_ticks[0] += 1
                idx = _debrief_idx[0]
                if idx < len(_debrief_items):
                    window._intelligent_screen.update_coaching(
                        f"[{idx+1}/{len(_debrief_items)}] {_debrief_items[idx]}", "green"
                    )
                    if _debrief_ticks[0] % 5 == 0:
                        _debrief_idx[0] += 1
                else:
                    _debrief_items.clear()
                return

            level = mode_mgr.coaching_level
            result = _eval_conditions(snap, level)
            if result:
                text, sentiment = result
                window._intelligent_screen.update_coaching(text, sentiment)
            else:
                window._intelligent_screen.update_coaching("", "dim")

        _condition_timer.timeout.connect(_condition_tick)
        _condition_timer.start()

        # Wire coaching level changes from K5 button
        mode_mgr.coaching_changed.connect(
            window._intelligent_screen.set_coaching_level
        )

    # Helper: speak through voice_mgr directly (headless) or window AudioPlayer (UI)
    def _speak(text, urgency="normal"):
        if window:
            window.queue_speech(text, urgency=urgency)
        elif voice_mgr:
            voice_mgr.speak(text)

    # --- Ambient condition tracking ---
    if db_store and ambient_source:
        def _on_ambient_reading(reading):
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
            # Voice handled by alert engine (rate-based, deduplicated, mode-aware).
            # condition_changed is for DuckDB logging only.

        ambient_source.reading_updated.connect(_on_ambient_reading)
        ambient_source.condition_changed.connect(_on_condition_changed)
        log.info("Ambient DuckDB recording enabled (1/min + change events)")

    elif ambient_source:
        # Voice handled by alert engine — condition_changed is legacy path
        pass

    # --- Ambient simulation lifecycle ---
    if args.sim_ambient and ambient_source:
        from sensors.ambient_simulator import AmbientSimulator
        if isinstance(ambient_source, AmbientSimulator):
            ambient_source.simulation_started.connect(
                lambda: _speak("Starting ambient weather simulation. Monitoring conditions.")
            )
            ambient_source.simulation_ended.connect(
                lambda: _speak("Ambient weather simulation complete.")
            )
            ambient_source.simulation_started.connect(
                lambda: log.info("SIM: Ambient weather simulation started")
            )
            ambient_source.simulation_ended.connect(
                lambda: log.info("SIM: Ambient weather simulation ended")
            )

            if not args.sim_voice:
                def _sim_done():
                    from PySide6.QtCore import QTimer as _QT2
                    _QT2.singleShot(8000, lambda: (
                        log.info("SIM: exiting after final speech"),
                        app.quit(),
                    ))
                ambient_source.simulation_ended.connect(_sim_done)

            from PySide6.QtCore import QTimer as _QT
            _QT.singleShot(20000, ambient_source.start)

    # --- Route LLM responses ---
    if voice_mgr:
        voice_mgr.response_ready.connect(lambda text: _speak(text))

    # --- UI-only wiring (waveform + echo protection) ---
    if window and voice_mgr:
        if hasattr(window, '_kisti_mode'):
            window._kisti_mode.set_voice_manager(voice_mgr)

        if voice_mgr._mic and hasattr(window, '_kisti_mode'):
            _kmode = window._kisti_mode
            if hasattr(_kmode, '_audio_player') and _kmode._audio_player:
                import threading as _echo_threading
                _kmode._audio_player.playback_started.connect(
                    lambda: voice_mgr._mic.pause()
                )
                def _echo_guard_resume():
                    _echo_threading.Timer(0.4, voice_mgr._mic.resume).start()
                _kmode._audio_player.playback_finished.connect(_echo_guard_resume)
                log.info("Echo protection: mic pauses during UI audio playback")

    if window:
        window.show()

    mode_label = "HEADLESS" if args.headless else mode_mgr.si_drive_mode.label
    log.info("KiSTI running — Mode: %s, Voice: %s, DuckDB: %s, Memory: %s, Zeus: %s, Sync: %s, CAN Out: %s, Ambient: %s",
             mode_label,
             "ON" if voice_mgr else "OFF",
             "ON" if db_store else "OFF",
             "ON" if edge_memory else "OFF",
             "ON" if zeus_sync else "OFF",
             "ON" if sync_mgr else "OFF",
             "ON" if can_output else "OFF",
             "SIM" if args.sim_ambient else ("YOCTO" if ambient_source else "OFF"))

    # Headless boot greeting — disabled (visual-only UX)
    # if args.headless and voice_mgr:
    #     ...


    # Demo mode: auto-start session after 5s so PatternEngine + data collection
    # run unattended (trade show / 30-min validation target)
    if args.demo and db_store:
        from PySide6.QtCore import QTimer as _DemoTimer
        _DemoTimer.singleShot(5000, mode_mgr.session_toggle.emit)
        log.info("Demo mode: auto-session start in 5s")

    # Run Qt event loop
    exit_code = app.exec()

    # Cleanup
    log.info("Shutting down...")
    if pattern_eng:
        pattern_eng.stop()
    if listener:
        listener.stop()
    if can_output:
        can_output.stop()
    if mock:
        mock.stop()
    if voice_mgr:
        voice_mgr.stop()
    if zeus_sync:
        zeus_sync.stop()
    if sync_mgr:
        sync_mgr.stop()
    if embedder:
        embedder.stop()
    if db_store:
        if session_id:
            db_store.end_session(session_id)
        db_store.close()
    if flir_reader:
        flir_reader.stop()
    if ambient_source:
        ambient_source.stop()
    mode_mgr.stop()
    alert_eng.stop()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
