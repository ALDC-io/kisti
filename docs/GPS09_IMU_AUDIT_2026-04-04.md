# GPS09 Pro & IMU — Full Data Usage Audit

**Date**: 2026-04-04 | **Audited by**: Claude Opus 4.6 (kisti-flir-07 session)

## Hardware

- **AiM GPS09 Pro Open**: 6-axis IMU (3 accel + 3 gyro @ 50Hz) + GPS (10Hz)
- **CAN IDs**: 0x6A4 (GPS pos), 0x6A5 (GPS ext), 0x6A6 (IMU accel), 0x6A7 (IMU gyro)
- **Status**: Software fully integrated. Hardware pending physical install.

## All Available Data Channels

### 0x6A4 — GPS Position (10 Hz)
| Field | DiffState | Type | Resolution |
|-------|-----------|------|------------|
| Latitude | `gps_latitude` | float | 0.00001 degrees |
| Longitude | `gps_longitude` | float | 0.00001 degrees |

### 0x6A5 — GPS Extended (10 Hz)
| Field | DiffState | Type | Resolution |
|-------|-----------|------|------------|
| Altitude | `gps_altitude_m` | float | 1m |
| Speed | `gps_speed_mps` | float | 0.01 m/s |
| Heading | `gps_heading` | float | 0.1 degrees |
| Satellites | `gps_satellites` | int | count 0-15 |
| Fix Quality | `gps_fix_quality` | int | 0=none, 1=2D, 2=3D |

### 0x6A6 — IMU Accelerometer (50 Hz)
| Field | DiffState | Type | Notes |
|-------|-----------|------|-------|
| Accel X | `imu_accel_x` | float (g) | Longitudinal (+ve = acceleration) |
| Accel Y | `imu_accel_y` | float (g) | Lateral (+ve = right turn) |
| Accel Z | `imu_accel_z` | float (g) | Vertical (~1.0 at rest) |

### 0x6A7 — IMU Gyroscope (50 Hz)
| Field | DiffState | Type | Notes |
|-------|-----------|------|-------|
| Gyro X | `imu_gyro_x` | float (deg/s) | Roll rate |
| Gyro Y | `imu_gyro_y` | float (deg/s) | Pitch rate |
| Gyro Z | `imu_gyro_z` | float (deg/s) | Yaw rate |

## Current Usage Matrix

| Channel | Logged | Visualized | Alerts | Coaching | Timing |
|---------|--------|------------|--------|----------|--------|
| Lateral G (Y) | YES | G-force circle + bar | High-G alert | Trail brake % | - |
| Longitudinal G (X) | YES | G-force circle only | Combined in high-G | NO | - |
| Vertical G (Z) | YES | NO | NO | NO | - |
| Gyro X (Roll) | YES | NO | NO | NO | - |
| Gyro Y (Pitch) | YES | NO | NO | NO | - |
| Gyro Z (Yaw) | YES | Sport bar only | NO | NO | - |
| GPS Lat/Lon | YES | NO | - | - | Sector crossing |
| GPS Speed | YES | NO | - | NO | - |
| GPS Heading | YES | NO | - | - | Track bearing |
| GPS Altitude | YES | NO | NO | NO | - |
| GPS Satellites | YES | NO | GPS loss only | - | - |
| GPS Fix Quality | YES | NO | - | - | - |

**Assessment: ~25% of sensor capability used in real-time analysis.**

## What Each Subsystem Uses

### Screens
- **Intelligent**: ZERO GPS/IMU visualization
- **Sport**: Lateral G bar, yaw rate bar, G-force circle (lat + lon), road condition zones
- **Sport Sharp**: G-force circle (lat + lon), road condition in sector strip, delta bar (from timing/GPS)

### Alert Engine (`alerts/alert_engine.py`)
- `_check_high_g()`: combined G = sqrt(accel_x² + accel_y²). Advisory at 1.0g, warning at 1.3g
- `_check_gps_stale()`: fires on GPS signal loss/acquisition (2s timeout)
- NO gyroscope alerts, NO altitude alerts, NO speed alerts

### Coaching (`coaching/technique_analyzer.py`)
- Uses ONLY `imu_accel_y` (lateral G) for trail braking quality
- NO longitudinal G analysis, NO gyro data, NO GPS data

### Timing (`timing/timing_manager.py`, `timing/track_learner.py`)
- GPS lat/lon for sector crossing detection
- GPS heading for track direction/bearing
- NO IMU for timing, NO altitude for elevation profiles

### Data Logging (`data/duckdb_store.py`)
- All 12 channels logged to telemetry table at ~20Hz
- This is solid — post-analysis has everything

### Parked Debrief (`analysis/parked_debrief.py`)
- NO GPS/IMU in post-session AI debrief (only engine health, knock, surface state)

## Identified Gaps

### Gap 1: GPS Speed vs Wheel Speed — Traction Loss Detection
Both values exist in DiffState. Comparing them detects:
- Wheelspin on acceleration
- Lockup on braking
- DCCD effectiveness validation

### Gap 2: Longitudinal G Analysis
Plotted on circle but never analyzed. Could provide:
- Peak braking G per lap (brake fade detection)
- Deceleration profiles (smooth vs panic braking)
- Acceleration envelope (traction limit under power)

### Gap 3: Gyro Yaw Rate vs GPS Heading Rate — Over/Understeer
Car rotating faster than heading change = oversteer. Slower = understeer.
Professional data systems (AiM, MoTeC) use this. We have both signals.

### Gap 4: Sector G-Force Consistency
Sectors are timed but G profiles not compared lap-to-lap.
"You carried 0.15g less through S3 this lap" is actionable coaching.

### Gap 5: Pitch Rate = Brake Quality
Smooth braking = low pitch rate. Threshold braking = clean pitch-up, hold, release.
Panic braking = spike. Free data from gyro_y.

### Gap 6: Corner Radius from GPS Trace
Auto-compute curvature from waypoints, compare actual line to optimal.
Foundation for racing line analysis.

### Gap 7: Altitude + Ambient Pressure = Density Altitude
Engine makes less power at elevation. GPS altitude + Yoctopuce pressure = real-time
density altitude. Matters on mountain passes (Rogers Pass in TODO).

### Gap 8: Braking Zone Detection (GPS Position + Longitudinal G)
Auto-detect where you brake, compare lap-to-lap.
"You braked 15m later on lap 4."

### Gap 9: Intelligent Screen — Zero GPS/IMU Visualization
The "guide mode" screen shows weather and voice ticker only.
Could show mini track map, G-force gauge, altitude profile, brake zone markers.

### Gap 10: Roll Rate for Body Dynamics
Roll rate correlates with suspension loading and weight transfer rate.
Combined with lateral G, reveals suspension setup quality.

## CAN Decode Details (reference)

### kisti_can.py
- `decode_gps_frame()` — lines 426-440
- `decode_gps_ext_frame()` — lines 443-464
- `decode_imu_frame()` — lines 467-479
- `decode_imu_gyro_frame()` — lines 482-494

### DiffStateBridge Update Methods
- `update_gps(latitude, longitude)` — lines 597-604
- `update_gps_ext(altitude, speed, heading, satellites, fix_quality)` — lines 606-623
- `update_imu(accel_x, accel_y, accel_z)` — lines 625-633
- `update_imu_gyro(gyro_x, gyro_y, gyro_z)` — lines 635-643

### Mock Generation
- `_imu_tick()` — lines 1321-1359
- Longitudinal accel from throttle/brake (0.5g accel, 1.2g braking)
- Lateral accel from cornering dynamics
- Gyro Z from heading delta / dt
- Gyro X from lateral_g * 5.0 (roll)
- Gyro Y from accel_x * 3.0 (pitch)
