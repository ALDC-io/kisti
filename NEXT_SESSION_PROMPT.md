# NEXT SESSION PROMPT — KiSTI

**Branch**: `kisti-headless` | **Dir**: `/home/aldc/repos/kisti` | **Jetson**: `ssh aldc@192.168.22.131` (pw: `aldc1234`)
**Tests**: `python3 -m pytest tests/ -q --tb=short --ignore=tests/test_voice_integration.py --ignore=tests/test_voice_pipeline.py`
**Test baseline**: 1214 tests
**Project tracker**: `/home/jkadmin/projects/active/2026-04-05-kisti-weather-intelligence/`

## What Was Done (2026-04-05 — Weather Intelligence Session)

Built and deployed complete dual-layer weather intelligence system:

1. **WeatherEngine** (`sensors/weather_engine.py`, 285 lines) — Rate-of-change threat detection with rolling 10-min window. 4 threat levels (CLEAR/CHANGING/RAIN_LIKELY/STORM). Multi-sensor fusion: rain, fog, snow, cold front.

2. **ECWeatherPoller** (`sensors/ec_weather.py`, 322 lines) — Background daemon polling api.weather.gc.ca. Warnings every 10 min, forecast every 15 min. Default city_id=bc-35 (Coquitlam). Graceful offline degradation.

3. **Dual-layer fusion** — EC warnings upgrade threat (watch→CHANGING, warning→RAIN_LIKELY) but never downgrade sensor readings. Hyperlocal Yoctopuce = ground truth; EC = prediction window extension.

4. **Alert routing** — 6 new weather alert types routed through voice_alert signal. Once-per-session deduplication. EC warnings fire through both Excelon display AND Link ECU MXG alerts.

5. **Screen display** — Intelligent screen: trend arrows (24px, 4px pen), weather threat text, EC warning banner, EC forecast. Sport/Sharp: weather pills (dark cockpit pattern).

6. **System** — GDM auto-login to kisti-session (no login prompt). SIGUSR1 handler for SI Drive mode cycling.

7. **Deployed** — Running on Jetson (PID 48058, fullscreen + mic). EC poller verified fetching. Stress-tested with frozen burgers (FLIR) and kettle steam (-8.9 hPa/hr STORM).

### Key Files Changed
| File | What |
|---|---|
| `sensors/weather_engine.py` | **NEW** — WeatherEngine with rolling window, trend detection, multi-sensor fusion |
| `sensors/ec_weather.py` | **NEW** — ECWeatherPoller background thread for Environment Canada API |
| `tests/test_weather_engine.py` | **NEW** — 11 tests |
| `tests/test_ec_weather.py` | **NEW** — 16 tests (parse, offline, fusion, alert routing) |
| `model/vehicle_state.py` | Added weather_trend + ec_weather fields to DiffState, bridge methods |
| `alerts/alert_engine.py` | 6 weather alert types, once-per-session dedup via _fired_types set |
| `ui/intelligent_screen.py` | Trend arrows, EC banner, threat text, baro color coding |
| `main.py` | WeatherEngine + ECWeatherPoller wiring, SIGUSR1 handler, removed old voice paths |

## Prioritized TODO

### 1. GPS-based EC region auto-lookup (when GPS09 Pro installed)
**Where:** `sensors/ec_weather.py:42-43` (DEFAULT_BBOX / DEFAULT_CITY_ID)
- Currently hardcoded to bc-35 (Coquitlam). Once GPS09 Pro CAN data flows, dynamically resolve EC city_id from lat/lon.
- EC API supports bbox query — use GPS coordinates directly for weather-alerts endpoint.
- City page lookup needs a city_id mapping (lat/lon → nearest EC station).

### 2. Threshold tuning against real driving data
**Where:** `sensors/weather_engine.py:16-20` (WINDOW_SHORT_S, MIN_SAMPLES_SHORT, THRESH_*)
- Current thresholds from meteorology literature. Need validation against real BC mountain weather.
- Log line: `Weather: CHANGING | baro -0.8 hPa/hr | hum 1.2%/hr | dew spread 12.0C`
- If arrows too twitchy: increase MIN_SAMPLES_SHORT (currently 30)
- If too slow: decrease WINDOW_SHORT_S (currently 600s)

### 3. EC forecast integration into Sport/Sharp screens
**Where:** `ui/sport_screen.py`, `ui/sharp_screen.py`
- Currently only Intelligent screen shows EC data. Add EC condition/forecast to Sport/Sharp.
- Follow dark cockpit: only show when conditions are abnormal.

### 4. Voice alert verification during real weather event
- Once-per-session dedup is working (kettle test confirmed). Need real rain/snow event validation.
- Monitor alert_engine logs during actual driving in weather.

## Architecture Notes

**Dual-layer design:**
- Hyperlocal (Yoctopuce) = ground truth at the car (1Hz, exact location)
- Regional (EC API) = prediction window extension (10-15 min lookahead, area-wide)
- Fusion rule: EC can upgrade threat, never downgrade. If sensors say STORM and EC says nothing → trust sensors.

**EC API:** api.weather.gc.ca — free, no auth, no rate limits. GeoJSON responses with nested `{value: {en: N}}` structure.

**Voice dedup:** AlertEngine._fired_types set tracks which alert types have fired. Prevents repetitive voice. display_alert and voice_alert signals skip duplicates. alert_fired still fires for DuckDB audit trail.

**Dark cockpit:** CLEAR = invisible. CHANGING = yellow text. RAIN_LIKELY/STORM = red text. EC warning = yellow banner. EC watch = blue banner. All auto-dismiss after 1 hour of stale EC data.

## Zeus Memory
- Session learning: `c0754bac-508f-4ac5-bb14-0fed72a7898d`
- Earlier session ZMID: `8e351653-1743-4b1c-b1de-5ebb3fdd40b7`
