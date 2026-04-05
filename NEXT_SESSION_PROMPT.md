# NEXT SESSION PROMPT — KiSTI kisti-flir-08

**Branch**: `kisti-headless` | **Dir**: `/home/aldc/repos/kisti` | **Jetson**: `ssh aldc@192.168.22.131` (pw: `aldc1234`)
**Tests**: `python3 -m pytest tests/ -q --tb=short --ignore=tests/test_voice_integration.py --ignore=tests/test_voice_pipeline.py`
**Baseline**: 1114 passed, 11 skipped

---

## Before starting work
1. `echo "KiSTI FLIR-08" > /tmp/tui-project-label`
2. Write phases to `/tmp/tui-phases.json`

## kisti-flir-07 summary (what was built)

### Zeus Proxy for Frontier Engine
- **Proxy routing**: `FrontierLLMEngine` now supports optional Zeus proxy for centralized auth/logging/cost tracking.
- **New params**: `proxy_url`, `proxy_key` in constructor. When both set, queries route through Zeus first, fall back to direct Anthropic on failure.
- **Methods added**: `_post_proxy()` (Zeus route), `_post_direct()` (Anthropic direct), `_parse_response()` (shared response parser with `_strip_markdown()`).
- **Audit header**: `X-Script-Name: kisti-frontier` sent to Zeus for per-device attribution.
- **Env vars**: `KISTI_PROXY_URL` and `KISTI_PROXY_KEY` read in `voice_manager.py`. Engine starts if EITHER `ANTHROPIC_API_KEY` or `KISTI_PROXY_KEY` is set.
- **8 new tests**: proxy routing, fallback to direct, X-Script-Name header, partial config, proxy-key-only start.
- **Proxy status logged**: `"proxy=https://zeus.aldc.io"` or `"direct"` in start message.

### Soak Test Results (13h uptime, 2026-04-04)
- **Memory pressure**: 344 MB available, 800 MB swap. KiSTI=3.78 GB (50%), whisper-server=2.09 GB (27%). Combined 77% of 7.4 GB RAM.
- **Stability**: No errors, no OOM, load steady at 6.0 across 1/5/15 min.
- **Cache**: 100 entries in frontier_cache, minimal activity (persona-only mode).
- **WiFi**: Not connected (wired ethernet only). Frontier requires WiFi for live queries.
- **DuckDB**: 7.6 MB total. 13,832 alerts, 7,642 ambient readings. No leaks.
- **Action needed**: Monitor swap growth. If >1.5 GB, consider whisper-server "small" model (saves ~1.5 GB).

## Activate Zeus Proxy on Jetson

Add to `~/k` launcher on Jetson:
```bash
export KISTI_PROXY_URL="https://zeus.aldc.io"
export KISTI_PROXY_KEY="$ZEUS_API_KEY"  # Same key — migration 053 grants proxy:anthropic scope
```

Verify after restart:
```
grep "proxy=" /tmp/kisti-session.log  # Should show "proxy=https://zeus.aldc.io"
```

Test with a voice question when on WiFi — Zeus audit should log it under "kisti-frontier" script name.

## Remaining from code review (kisti-flir-08 work)

### High priority
1. **Wake Word Integration** — pkl model at `/data/models/hey_kisti.pkl` (99.2% accuracy) not integrated into `mic_capture.py`. Needs pkl verifier layer alongside OWW. Record 50 real "Hey KiSTI" samples from JK for retraining. Alternative: full ONNX training via Colab.
2. **Memory pressure mitigation** — 314 MB available is tight. Options: (a) whisper-server "small" model saves ~1.5 GB, (b) investigate KiSTI 3.78 GB RSS (seems high for Python), (c) Python gc.collect() periodically.

### Medium priority
3. **Udev rule for FLIR USB** — `ACTION=="add", ATTR{idVendor}=="1e4e", RUN+="/bin/chmod a+w %S%p/authorized"`. Eliminates sudo dependency.
4. **_label_blobs performance** — pure Python flood fill on 19K pixels. Add hot_count ceiling (>30% = skip) or use scipy.ndimage.label.
5. **Auto-detect device safety** — opening all /dev/videoN can steal other sensor handles. Add VID check or --flir-device flag.
6. **Two status lines on Intelligent screen** — user reported duplicate text at bottom. Investigate coaching bar vs voice ticker overlap.

### Nice to have
7. **Rogers Pass route tag** — auto-tag sessions with route name.
8. **Debrief display on Intelligent screen** — currently coaching bar only (24px, single line). Could use larger overlay when parked.
9. **Visual verification on Jetson** — rsync and test zone bar rendering on Strada 7" display. Check sunlight visibility.

## Key files
- `voice/frontier_engine.py` — proxy routing (_post_proxy, _post_direct, _parse_response)
- `voice/voice_manager.py:273-280` — proxy env var wiring
- `ui/road_condition.py` — shared paint functions (zone tint, edge glow, zone bar)
- `model/vehicle_state.py` — per-zone classification, classify_surface()
- `alerts/alert_engine.py` — grip removed from voice, ambient checks
- `sensors/flir_lepton_reader.py` — _consecutive_warm reset
- `tests/test_frontier_engine.py` — 36 tests (8 proxy routing)

## Don't Repeat
- FLIR `temps_updated` sends `RoadSurfaceTemps` object, not 3 floats
- `_last_emit` must be instance-level on PatternEngine, not class-level
- `avg > 0` guard blocks sub-zero detection → use `!= 0.0`
- Two KiSTI processes fight for `/dev/video0` → kill ALL before restart
- `CAP_PROP_READ_TIMEOUT_MSEC` is silently ignored by V4L2 backend
- PureThermal lockup can survive USB reset — worker thread retries with backoff
- GDM auto-restarts kisti-session on process exit — don't `kill -9` the session itself
- Dew point in test fixtures: dew_point=10.0 + road=3.0 → LOW_GRIP (not COLD). Use dew_point=0.0 for COLD tests
- LOW_GRIP bypasses hysteresis (safety-critical) — tests must account for this
- Rsync to `~/repos/kisti` on Jetson, NOT `~/kisti`
- `_check_grip` must be in sensor-independent section (before `is_engine_stale` gate)
- Don't add `time.sleep()` in FLIR worker thread — `cap.read()` blocks at native frame rate
- TTS pronunciation: "Kissty" not "Keesty Eye" (voice/tts_engine.py TTS_SUBSTITUTIONS)
- `classify_surface()` is the single source of truth for surface classification thresholds
- Per-zone hysteresis is independent — each zone has its own counter/pending state
- `_consecutive_warm` must reset after emit or it fires every frame
- `_gps_was_live` is a dedicated bool, NOT stored in `_last_alert` dict
- When editing on `main` branch then switching to `kisti-headless`, stash pop creates merge conflicts. Always start on the right branch.
