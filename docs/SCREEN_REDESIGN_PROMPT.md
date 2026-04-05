# KiSTI Screen Redesign — Full Sensor Utilization

## Prompt for Next Session

Pick up KiSTI screen redesign. Read `docs/GPS09_IMU_AUDIT_2026-04-04.md` first — it contains a full audit of every sensor channel available vs what's actually used. We're at ~25% utilization of the GPS09 Pro + IMU. This session redesigns all 3 screens to close that gap.

## Context: The Car

2014 Subaru WRX STI (EJ257 turbo, AWD, DCCD). Full build: IAG 750 short block, BCP X400 turbo, ID1300 injectors, FMIC, Fortune Auto coilovers. See `data/build_record.py` for all thresholds.

## Context: Two Displays, Synchronized

The driver sees TWO screens that change together when the SI Drive knob rotates:

### Display 1: AiM Strada 7" Street Edition (CAN-native)
- AiM's own firmware, configured via Race Studio
- Shows: RPM bar/needle, boost gauge, speed, gear, lambda/AFR, oil pressure, oil temp, coolant temp, fuel pressure, battery voltage
- Shift lights: 10 RGB LEDs across top (KiSTI drives these via CAN)
- GPS09 Pro plugs directly into Strada's CAN — Strada has its own lap timer, track map, min/max logging
- **This is the "traditional gauge cluster" — AiM does this better than we ever could**

### Display 2: Kenwood DMX809S (6.75", 800x480, HDMI from Jetson)
- KiSTI's Qt dashboard — our code, our screens
- **This is where KiSTI adds value the Strada CANNOT**
- SI Drive knob switches both displays in lockstep

### The Rule: KiSTI Shows What AiM Cannot
- AiM handles: RPM, boost, speed, gear, lambda, oil, coolant, fuel pressure, voltage, basic lap timer, track map
- KiSTI handles: FLIR thermal, road conditions, IMU analysis, driving technique, voice interaction, alerts with context, debrief, coaching, body dynamics, grip analysis
- **NEVER duplicate what AiM already shows** — the driver has both screens in their line of sight

## Context: Sensors Available to KiSTI

All of these feed into DiffState via CAN or USB:

### From Link G5 Neo 4 ECU (CAN)
- RPM, boost (kPa), throttle %, coolant temp, oil temp, oil pressure (150 PSI sensor), fuel pressure, battery voltage, injector duty, knock count, intake air temp, flex fuel %, lambda, gear position
- DCCD command %, front/rear wheel speeds (4 individual), ABS active, VDC/TC active, brake pressure
- Steering angle, steering rate

### From AiM GPS09 Pro (CAN, 50Hz IMU / 10Hz GPS)
- **Accelerometer**: X (longitudinal), Y (lateral), Z (vertical) — 50Hz, 0.001g resolution
- **Gyroscope**: X (roll rate), Y (pitch rate), Z (yaw rate) — 50Hz, 0.01 deg/s resolution
- **GPS**: lat/lon, altitude, speed, heading, satellites, fix quality — 10Hz

### From FLIR Lepton (USB, 9Hz)
- 3-zone road surface temperatures (left/center/right)
- Per-zone surface classification (DRY/WET/COLD/LOW_GRIP)
- Warm object detection (brake heat, exhaust, animals)

### From Yoctopuce Yocto-Meteo-V2 (USB, 1Hz)
- Ambient temperature, humidity, barometric pressure
- Derived: dew point, density altitude (with GPS altitude)

## Design Philosophy

### From Previous Sessions (JK-approved principles)
1. **One screen per mode, no sub-pages.** SI Drive knob is the only navigation. Everything fits on ONE 800x480 screen per mode.
2. **Dark cockpit philosophy.** Normal = invisible. Only abnormal states demand attention. DRY zones are nearly transparent. Warnings escalate visually.
3. **Pre-attentive features.** Color hue as primary encoding. Motion (pulse) for highest threat only.
4. **Aviation HUD / TCAS / RWR principles.** Status-by-exception. Discrete states for decision-making (not continuous gradients). Declutter: suppress nominal.
5. **Voice tiers match screen tiers.** Intelligent=personality+data, Sport=clinical data only, Sport Sharp=emergency alerts only.

### Mode Personalities (from RS3 design)
- **Intelligent** = Guide/Explorer. "Tell me everything." Full info, weather, coaching, voice interaction. The driver is cruising, learning, or parked reviewing data. This is the ONLY mode where general information belongs.
- **Sport** = Co-Driver. "What do I need to know right now?" Focused on dynamics, technique, and conditions. Data the MXG Strada can't show. No fluff.
- **Sport Sharp** = Race Engineer. "Am I faster? Am I safe?" Timing delta, G-envelope, critical safety only. Absolute minimum visual noise. Every pixel must earn its place.

## Research Task

Before designing layouts, research these topics thoroughly and present findings:

1. **Professional motorsport data displays** — How do AiM Race Studio, MoTeC i2, Pi Toolbox display IMU data to engineers and drivers? What visual idioms work at speed? Focus on what they show DURING driving (not post-session analysis).

2. **G-force envelope visualization** — What's the best way to show combined lat/lon G at a glance? Friction circle vs diamond vs numeric? Trail length? Update rate for 50Hz data on a 20Hz paint loop?

3. **Oversteer/understeer indicators** — Professional systems compare yaw rate (gyro Z) to expected yaw from GPS heading rate. How is this visualized? Simple bar? Color shift? Is it useful in real-time or only post-analysis?

4. **Brake quality visualization** — Pitch rate (gyro Y) and longitudinal G show braking technique. How do pro systems visualize this? Is a brake trace useful at-a-glance?

5. **Traction loss detection** — GPS speed vs wheel speed comparison. How is this shown? Warning threshold? Relationship to DCCD display?

6. **Altitude/density altitude** — Is this useful in real-time? How do rally/hillclimb systems present it? Worth screen space?

7. **Corner classification from GPS + G** — Auto-categorize corners by radius/G. "Fast right" vs "slow hairpin." Useful for sector comparison? 

8. **Sector G-force profiling** — Overlaying G profiles lap-to-lap. Is this useful during driving or only post-session? If during, how to simplify to a glance?

9. **What makes the difference between "data display" and "making the driver better"?** — The goal is not to show data. The goal is to help the driver improve. What feedback loops actually change driver behavior? Research sports science, coaching theory, real-time biofeedback.

## Design Deliverable

After research, produce a complete screen redesign plan for all 3 modes:

### For each screen, specify:
- ASCII layout map (800x480, like the maps in this conversation)
- Every element: position, size, data source, color logic, stale behavior
- What's from GPS09 IMU that wasn't there before
- What was removed and why (remember: don't duplicate AiM Strada)
- How it makes the driver better (not just "shows data")
- Coaching feedback integration points
- Dark cockpit behavior (what's invisible when normal)

### Cross-screen consistency:
- Road condition (FLIR + ambient) presentation across all 3
- Edge glow behavior
- Voice ticker placement
- Safety vital presentation (dim until warning)

### What stays on AiM Strada (do NOT put on KiSTI):
- RPM, boost, speed, gear — Strada has beautiful dedicated gauges
- Lambda/AFR — Strada shows this natively
- Basic oil/coolant/fuel numbers — Strada handles these
- Simple lap timer — Strada has its own from GPS09

### Key files to read before designing:
- `docs/GPS09_IMU_AUDIT_2026-04-04.md` — sensor audit (this session's output)
- `ui/intelligent_screen.py` — current Intelligent layout
- `ui/sport_screen.py` — current Sport layout  
- `ui/sharp_screen.py` — current Sport Sharp layout
- `ui/road_condition.py` — shared paint functions
- `ui/theme.py` — color palette
- `model/vehicle_state.py` — DiffState fields (all sensor data)
- `coaching/technique_analyzer.py` — current coaching system
- `alerts/alert_engine.py` — alert thresholds
- `data/build_record.py` — vehicle baseline targets
- `timing/timing_manager.py` — lap timing system
- `NEXT_SESSION_PROMPT.md` — current state and don't-repeat list

### Constraints:
- 800x480 pixels per screen (Kenwood DMX809S)
- 20Hz paint loop (QPainter, no OpenGL)
- Dark background (STI gauge cluster aesthetic — see theme.py)
- Must work with mock data (no real CAN yet)
- Must handle stale data gracefully (sensors disconnect)
- Tests must be written for all new analysis functions
- Shared rendering functions go in `ui/road_condition.py` or a new shared module

## Success Criteria

The redesign is successful when:
1. Every GPS09 Pro channel is either visualized, analyzed, or explicitly justified as post-analysis-only
2. The technique analyzer uses longitudinal G, gyro data, and GPS speed (not just lateral G)
3. Each screen answers the mode's core question without duplicating AiM Strada
4. A driver who has never seen the system can understand each screen in <2 seconds
5. The screens make the driver measurably better (faster lap times, smoother inputs, better brake points)
