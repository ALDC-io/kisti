# KB: STI Task List — Full Consolidated Set
*JK CONFIDENTIAL | Captured: 2026-04-17 / Updated: 2026-04-18*
*Source: 2014 Subaru WRX STI (GR chassis) project — ~460 HP, track + road mission car*
*Dash: AiM MXG 1.3 Strada | ECU: Link G5 Voodoo Neo 4 | PDM: Razor | Jetson: Orin Nano 8GB (KiSTI)*
*Track use: Mission Raceway, The Ridge (~every 2 months) | Road: Rogers Pass → Banff May 2026 first field mission*
---
## Item 1 — Redline increase
Hold gears longer through corners — reduce mid-turn upshifts on track.
---
## Item 2 — ECU safety strategy
Monitor & protect:
- Oil pressure
- Fuel pressure
- Boost
- Coolant temp
- Lambda
Cut/limit triggers on out-of-range values before damage occurs. See Item 16 for the full alert framework that integrates these protections with driver communication.
---
## Item 3 — ECU map structure (3 modes via SI-Drive)
**Selection mechanism: OEM SI-Drive 3-position selector (I / S / S#)**
- Link G5 reads SI-Drive position via Subaru CAN signal (or hardwired input)
- Map switch takes effect on next full throttle lift or after 2-second dwell (prevents mid-corner surprise swaps)
- Selection broadcast on CAN for KiSTI to tag DuckDB rows with active map context
- Driver's hand already lives on SI-Drive — zero new muscle memory required
**Mapping:**
| SI-Drive | ECU map | Character |
|---|---|---|
| **I (Intelligent)** | **Limited (Learner)** | Reduced power, soft throttle, RPM cap, stricter safety |
| **S (Sport)** | **Base** | Balanced throttle, full power, daily usable, FFS enabled |
| **S# (Sport Sharp)** | **Aggressive** | Very direct throttle, fastest response, full boost, FFS + optional light ALS |
Tire profile (Item 14) is orthogonal — 3 maps × 3 tires = 9 effective calibrations.
---
## Item 4 — PDM (Razor) power + protection strategy
- **Inverter management through the PDM** — the 12V → AC inverter that feeds the Jetson and laptop must be gated by the PDM, not wired to a raw ignition-sense relay. Routing through the PDM enables: post-crank delayed startup (inverter only comes up after the engine is running, not during cranking when voltage sags); graceful shutdown sequencing (PDM signals the Jetson to save state and quiesce, waits for acknowledgment, then kills inverter power); low-voltage cutoff protection (PDM drops the inverter before the battery drains below starting threshold); and coordinated behavior with turbo-cooldown and ignition-on windows.
- Delayed startup (post-crank) — PDM holds non-essential loads including the inverter until the alternator is producing stable voltage (typically 1–2s after first successful fire)
- Controlled shutdown (graceful Jetson power-off) — PDM asserts a shutdown-request line to the Jetson, waits for Jetson acknowledgment (max 30s), then cuts power. Prevents DuckDB corruption and allows the FLIR/CAN subsystems to flush cleanly.
- Low-voltage cutoff (battery protection) — configurable threshold (e.g., 11.8V) below which PDM sheds loads including the inverter
- Crank protection (drop non-critical loads during start)
- Turbo cooldown: hold ignition + water pump circulation 60–120s after key-off if oil temp > 100°C (ties to Item 15)
---
## Item 5 — Torque & boost control (integrated)
- Gear-based boost targets
- DBW torque shaping: tip-in, mid-corner, reapplication
- Fueling integration: 93 / E85, lambda targets
- Smooth boost ramp / traction-aware behavior
- Launch control: tire-dependent behavior (LC only — extended to full system-wide tire awareness in Item 14)
---
## Item 6 — Traction / stability strategy
AWD torque split, ABS, and VDC behavior coordinated with the 3 ECU maps and tire profile.
**DCCD (Driver Controlled Centre Differential):**
- Open / auto / locked preload per SI-Drive mode
- Auto mode baseline; Sport Sharp favors rear bias; Intelligent favors more stability (more locked)
- Tire profile (Item 14) overlays: winter = more locked, track = more open for rotation
**ABS / VDC thresholds:**
- Earlier intervention on winter tires (low grip ceiling)
- Later intervention on R-comps (can tolerate more slip before panic)
- VDC disable option on Sport Sharp + Track tire profile for dedicated track use
**Integration points:**
- All thresholds readable from Link G5 and adjustable per calibration table
- Transition logic avoids mid-corner surprise changes (same dwell rule as Item 3)
- KiSTI logs every DCCD state change and VDC intervention to DuckDB
**Cross-references:**
- Item 3 (ECU map)
- Item 14 (tire profile)
- Item 16 (VDC intervention fires as T1/T2 advisory)
---
## Item 7 — Data acquisition integration
KiSTI DuckDB pipeline specification — what channels, what rates, what transport.
**Transport chain:**
Link G5 → CAN1 at 1 Mbit/s → Korlan USB2CAN adapter → Jetson Orin Nano (slcan0) → DuckDB ingestion.
**Channel inventory (baseline — to be expanded):**
| Channel | Source | Sample rate | Critical for |
|---|---|---|---|
| RPM | Link G5 | 100 Hz | All anomaly models |
| TPS / throttle | Link G5 | 100 Hz | Tip-in behavior |
| MAP / boost | Link G5 | 100 Hz | Boost anomalies |
| Oil pressure | Link G5 | 50 Hz | Safety (Item 16) |
| Oil temp | Link G5 | 10 Hz | Warmup (Item 15) |
| Coolant temp | Link G5 | 10 Hz | Cooling / Item 16 |
| Lambda (front/rear) | Link G5 | 100 Hz | Fueling / knock |
| Knock / IAM | Link G5 | 100 Hz | Knock precursor ML |
| Wheel speeds (4×) | Subaru CAN or Link | 50 Hz | Grip / VDC analysis |
| Steering angle | Subaru CAN | 50 Hz | Driver input |
| Brake pressure | Brake sensors (front/rear) | 50 Hz | Braking behavior |
| GPS lat/lon/speed | GPS09 when installed | 10 Hz | Track mapping |
| IMU (3-axis G) | MXG internal | 50 Hz | Cornering load |
| Ambient temp | Yocto-Meteo-V2 | 1 Hz | Environmental |
| FLIR surface temp | FLIR Lepton | 9 Hz | Ice detection |
| SI-Drive position | Subaru CAN | 1 Hz | Map context tag |
| Tire profile | MXG menu → CAN | On change | Calibration tag |
**Cross-references:**
- Item 8 (anomaly detection consumes this)
- Item 16 (alert system consumes this)
- KiSTI Zeus memory `db021919-0623-4bd3-bed2-dbb5f070877a` for CAN setup
---
## Item 8 — Anomaly detection channels (KiSTI ONNX models)
ML model targets and input features for the KiSTI anomaly detection pipeline.
**Tier 1 models (highest-value, earliest to ship):**
| Model | Target | Input features |
|---|---|---|
| **Knock precursor** | Predict knock 100–500ms before it happens | RPM, MAP, lambda, IAM, coolant temp, IAT, fuel pressure |
| **IAM decay** | Detect long-term tune degradation | IAM trend, knock events per drive, fuel quality context |
| **Grip loss signature** | Detect loss of traction before VDC fires | Wheel speeds delta, steering angle, lateral G, throttle |
| **Oil pressure anomaly** | Detect anomalous pressure drops before safety threshold | Oil pressure, RPM, oil temp, load |
**Tier 2 models (after baseline sessions collected):**
- Lambda drift (injector wear, fuel quality shifts)
- Fuel pressure anomaly (pump fatigue, filter clogging)
- Coolant system anomaly (pump, thermostat, airflow)
**Context features (attached to every model input):**
- SI-Drive position (Item 3)
- Tire profile (Item 14)
- Ambient temp + humidity (Yocto)
- Session type (cold start / street / track)
**Output format:**
ML detections fire into Item 16 alert framework as elevated-priority alerts with confidence score. Each detection logged to DuckDB with full input feature vector for post-hoc analysis.
**Cross-references:**
- Item 7 (data source)
- Item 16 (alert delivery framework)
- KiSTI repo owns ONNX model training pipeline
---
## Item 9 — Gear / shift strategy
Driver-assist behaviors around gear changes, per SI-Drive mode.
**Flat-foot / no-lift shift:**
- **I mode:** disabled (protect driveline for learners)
- **S mode:** enabled with standard cut duration
- **S# mode:** enabled with aggressive cut duration for minimal torque interruption
**Rev-match on downshift:**
- **I mode:** enabled, generous blip window (helps smooth shifts for learners)
- **S mode:** enabled with moderate blip
- **S# mode:** disabled (driver heel-toes — don't interfere with intent)
**Shift cut duration (ignition cut during upshift under WOT):**
- **I mode:** N/A (flat-foot disabled)
- **S mode:** ~80ms (smooth, protects driveline)
- **S# mode:** ~50ms (quicker shift, more stress accepted)
**Gear-dependent shift light thresholds:**
Per Item 16 — SI-Drive changes thresholds, not whether shift lights work.
**Cross-references:**
- Item 3 (SI-Drive modes)
- Item 16 (shift light behavior)
---
## Item 10 — Cooling strategy
Fan control and coolant/oil temp thresholds — street vs track differentiated.
**Electric fan control tables:**
- **Street mode:** fan on at 95°C coolant, off at 88°C
- **Track mode:** fan on at 88°C coolant (pre-emptive), off at 82°C — keeps coolant lower before the track session heats everything up
- **Cold start mode:** fan disabled until coolant > 40°C (don't fight warmup)
**Oil temp-driven actions:**
- See Item 15 for warmup
- See Item 16 for over-temp alerts
- Optional: oil cooler bypass thermostat behavior (if fitted)
**Ambient-aware (Yocto integration):**
- Hot ambient (>30°C) + track mode = fan thresholds lowered another 2°C
- Cold ambient (<5°C) + warmup = fan stays off longer
**Mode source:**
Track vs Street vs Cold start determined by combination of SI-Drive position, tire profile (Item 14), and KiSTI session classification (GPS speed patterns, location geofencing around known tracks).
**Cross-references:**
- Item 2 (ECU safety)
- Item 15 (cold start)
- Item 16 (cooling alerts)
---
## Item 11 — Diagnostics & fault handling
CEL behavior, limp modes, and the relationship between stock DTCs, Link G5 faults, and KiSTI logging.
**Fault source hierarchy:**
- **Link G5 faults:** primary — any ECU-detected condition (sensor fail, pressure deviation, knock, etc.)
- **Subaru body ECU DTCs:** secondary — ABS, airbag, body electrical (still readable over OBD if fitted)
- **KiSTI detected anomalies:** tertiary — ML-detected patterns not flagged by ECU (see Item 8)
**CEL behavior:**
- Stock CEL repurposed for Link G5 fault indication via digital output
- Steady CEL: non-critical fault (log only, no derate)
- Flashing CEL: active limp mode engaged (Item 2 protection firing)
- CEL also mirrored to MXG alarm LED 8 (KiSTI/system status) for redundancy
**Limp mode tiers (ties to Item 16 T3/T4 ECU response):**
- **Soft limp:** boost cut 30%, no RPM cap — preserves driveability to get home
- **Medium limp:** boost cut 50%, RPM cap 4,500 — safety-first but still mobile
- **Hard limp:** boost cut 80%, RPM cap 3,500, ignition retard — engine preservation mode, get to side of road
**Fault logging to KiSTI DuckDB:**
Every Link G5 fault event captured with:
- Fault code + description
- Values of all monitored channels at trigger
- Driver action (throttle/brake/steering) at trigger
- Session context (SI-Drive, tire profile, location)
- Resolution time + condition
**Post-drive review:**
KiSTI generates fault summary report per session — pattern detection across sessions (e.g., "lambda drift fault has triggered 3× in last 5 sessions, pattern suggests pump wear").
**Cross-references:**
- Item 2 (ECU safety)
- Item 8 (ML anomaly detection)
- Item 16 (alert framework delivers fault communication)
---
## Item 12 — Dash integration (MXG 1.3 Strada channel mapping)
RS3 channel configuration — what ECU data drives which dash element.
**Primary gauge page channels (from Link G5 via CAN):**
- RPM → tachometer (main gauge + shift lights)
- Speed → digital readout (wheel speed preferred over GPS for latency)
- Gear → gear indicator
- Coolant temp → bar + digital
- Oil temp → bar + digital + Item 15 icon logic
- Oil pressure → bar + digital
- Boost → bar + digital
- Lambda → bar + digital
- Battery voltage → digital
- IAT → digital (secondary page)
- Fuel pressure → digital (secondary page)
**Alarm thresholds (RS3 configuration):**
All thresholds from Item 16 implemented as RS3 alarm conditions with tier-appropriate colors, flashing, and text messages.
**Page layout:**
- **Page 1 — Street:** gauges + large speed/RPM, minimal telemetry
- **Page 2 — Track:** lap timing, delta, gear, RPM, predictive time, minimal gauges
- **Page 3 — Diagnostic:** all ECU values + KiSTI system status
- **Page 4 — Warmup:** oil temp prominent, cold start progress indicators, Item 15 blue/green state visible
Page switching via keypad buttons 2 (forward) and 3 (back).
**Custom CAN IDs (KiSTI-originated):**
- Tire profile selection (Item 14) on custom CAN ID
- KiSTI system status (sensor health, thermal, recording state)
- KiSTI anomaly detection outputs (Item 8) — fire alarms into MXG framework
**Cross-references:**
- Item 16 (full alert framework implementation)
- RS3 overlay work (cfg_20260401_152932)
- KiSTI CAN setup Zeus memory `db021919-0623-4bd3-bed2-dbb5f070877a`
---
## Item 14 — Tire-aware behavior (beyond launch control)
Tire profile is a **second calibration dimension** overlaid on top of the 3 ECU maps. Effective calibrations = 3 maps × 3 tires.
**Tire profiles:**
- **Winter** — Nokian Hakkapeliitta SN3 on Method 18s (Rogers Pass, cold road)
- **Street** — summer street tire, PS4S-class (daily, Duffey, road missions)
- **Track** — R-comp / track tire (Mission Raceway, The Ridge)
**Systems that adapt per tire profile:**
- Boost targets per gear (cap on winter, full on track)
- DBW tip-in aggressiveness (softer on low-grip)
- DCCD preload (open on dry track, locked on snow)
- VDC/ABS thresholds (earlier on winter, later on R-comps)
- Torque limits in 1st/2nd gear (cap on winter to prevent wheelspin cascade)
**Selection method: MXG menu system**
- Lives in MXG configuration menu, NOT on a keypad button
- Accessed via MXG's native menu navigation
- Selection broadcast on custom CAN ID, read by Link G5 and KiSTI
- Persists across power cycles
- Changed only when tires are physically changed (quarterly, not per-drive)
**Rejected: auto-detection.** Violates No Hallucinations and Data-Driven principles. Car should not guess its own tires.
**Cross-references:**
- Item 3 (ECU map structure — tire profile is orthogonal dimension)
- Item 5 (launch control already tire-dependent — this extends logic system-wide)
- Feeds KiSTI anomaly detection (tire context is feature input for ONNX models)
---
## Item 15 — Cold start / warmup strategy
Protect turbo, oil system, and driveline during cold start — especially Rogers Pass sub-zero conditions (May 2026 mission).
**Core ECU protections:**
- Oil pressure-based RPM cap (~3,500) until oil pressure stabilizes and oil temp crosses threshold
- Boost lockout until coolant temp threshold
- Idle speed elevation (1,100–1,200 RPM cold, drop to 800 when warm)
- Fan disable on cold start
- Turbo cooldown logic: PDM holds ignition + water pump 60–120s after key-off if oil temp > 100°C
**Cold-soak specific (Rogers Pass):**
- Below -5°C ambient, extend warmup window
- KiSTI monitors Yocto ambient + coolant delta, warns on aggressive throttle during warmup
- Log every cold start as distinct session type in DuckDB
**Oil temp dash indicator (EJ257-calibrated thresholds per community research):**
| State | Oil temp | Meaning |
|---|---|---|
| **Blue icon** | < 60°C (< 140°F) | Wait — do not drive |
| **Green icon** | 60–90°C (140–195°F) | Drive, no WOT yet |
| **No icon** | 90–120°C (195–250°F) | Full operating, send it |
| **Red icon (warning)** | 120–130°C | Back off, approaching limit |
| **Red flashing (critical)** | > 130°C | Emergency — reduce load now |
Note: On EJ257, oil reaches operating temp significantly later than coolant. Coolant-based warmup is misleading on this engine; oil-temp-based is genuinely more accurate.
**Cross-references:**
- Item 2 (ECU safety)
- Item 4 (PDM — turbo cooldown)
- Item 16 (concrete first implementation of the broader alert framework)
---
## Item 16 — Driver warning alert system
A unified, tiered alert framework spanning MXG dash, KiSTI voice, and ECU response. All alerts logged to DuckDB with timestamp, severity, channel, value, and resolution time.
### Severity tiers (aviation-derived)
| Tier | Name | Meaning |
|---|---|---|
| T0 | Info | State change, no action needed |
| T1 | Advisory | Pay attention soon |
| T2 | Caution | Action recommended |
| T3 | Warning | Action required |
| T4 | Emergency | Immediate — engine at risk |
### Alert catalog (monitored channels → thresholds)
- **Oil temp:** T1 110°C / T2 120°C / T3 130°C (boost soft cut) / T4 140°C (limp)
- **Oil pressure:** T2 <20psi hot idle / T3 <10psi idle / T4 <5psi any (ignition cut request)
- **Coolant temp:** T1 100°C / T2 105°C / T3 110°C (boost cut) / T4 115°C (limp)
- **Knock / IAM:** T2 1 event / T3 3 in 30s (timing pull) / T4 IAM decay > 2 (limp)
- **Lambda:** T3 lean > 0.90 at WOT (boost cut) / T4 > 0.95 (limp)
- **Boost:** T2 +2 psi over target / T3 +4 psi sustained (cut) / T2 -3 psi at WOT (underboost)
- **Trans temp:** T1 110°C / T2 130°C / T3 150°C
- **Electrical:** T1 <12.8V / T2 <12.0V / T3 <11.5V (PDM shed loads)
- **KiSTI self-monitoring:** T1 sensor dropout / T2 CAN errors / T3 Jetson thermal
- **Environmental:** T1 ambient <2°C + humidity >85% / T2 FLIR surface <0°C / T3 confirmed ice
### Cross-channel correlation (KiSTI, not ECU)
- Oil temp T2 + WOT sustained 30s → elevate to T3
- Lambda lean T2 + knock T2 → elevate to T3 (compounding damage)
- Coolant T2 + ambient >30°C + track mode → elevate voice urgency only
ECU handles single-channel protections; KiSTI handles correlated intelligence.
### Alert prioritization (FAA-pattern, one alert at a time on voice/tone)
Priority order, highest first:
1. T4 Emergency
2. T3 Critical
3. Knock events (always elevate — time-critical damage)
4. Oil pressure (always elevate — catastrophic if ignored)
5. Coolant
6. Oil temp
7. Lambda
8. Boost / fuel pressure
9. Electrical
10. KiSTI self-monitoring
11. Environmental
Only highest-priority active alert speaks and tones. Lower-priority alerts show on visual only. When higher alert resolves, next-highest takes over.
### Phase-based alert inhibition (aviation-pattern)
Suppress non-critical alerts during phases where they'd distract more than help:
- **Cold start phase** (first 30s after ignition): suppress T1/T2 except safety-critical
- **High-load phase** (WOT + >80% steering lock OR >1.0g lateral): suppress T1/T2
- **Shutdown cooldown phase**: T1 turbo cooldown only
T3/T4 ALWAYS fire regardless of phase.
---
### Delivery channels — MXG 1.3 Strada hardware
**Hardware available:**
- 7" TFT display (800×480)
- 10 RGB shift lights (top of dash, peripheral vision)
- 8 RGB alarm LEDs (configurable priorities, solid/flashing with text messages)
- 1-AMP digital output (external buzzer capable)
- Native CAN output for KiSTI consumption
### Layer 1: Alarm LEDs (8 RGB, dedicated, persistent)
One LED per persistent monitored condition. Driver learns position-to-condition mapping.

**Actual dash layout** (supersedes earlier generic spec — reflects MXG icon positions on this car):
| LED | Position      | Condition                | Colors |
|---|---|---|---|
| 1 | Top-left      | Left turn signal         | Green continuous (mirrors signal blink) |
| 2 | Upper-left    | *TBD*                    | — |
| 3 | Lower-left    | *TBD*                    | — |
| 4 | Bottom-left   | Engine (oil press loss)  | off / Red / Flash red |
| 5 | Top-right     | Right turn signal        | Green continuous (mirrors signal blink) |
| 6 | Upper-right   | Oil temp                 | Blue / Green / off / Red / Flash red |
| 7 | Lower-right   | Coolant temp             | off / Red / Flash red |
| 8 | Bottom-right  | *TBD*                    | — |

**Remaining channels from original spec need LED slot assignment:** knock/IAM, lambda/AFR, boost, electrical/PDM, KiSTI status. Candidates: LEDs 2, 3, 8 — plus any freed by removing turn-signal LEDs if body CAN proves unreliable. Decide once Item 18 body-CAN integration lands.

Independent and persistent — multiple can be lit simultaneously.
### Layer 2: TFT display
- Normal: active gauge page
- T2+: banner at top/bottom with condition + value
- T4: full-screen alarm page for 3s, then returns to gauges with persistent banner
- Includes shift light graphic strip (recovering conventional shift indication when physical shift lights are busy with voice waveform)
### Layer 3: Shift lights (10 RGB) — context-aware allocation
**Priority-ordered, highest wins:**
1. **T4 Emergency sweep** — red flash sweep, persistent
2. **T3 Warning sweep** — orange flash sweep, persistent
3. **Shift indication** — when RPM > active mode's gear threshold (universal across SI-Drive modes)
4. **Safety voice waveform** (Channel A, red) — during safety speech, always renders
5. **Conversational voice waveform** (Channel B, blue/green) — only when unmuted AND speaking
6. **Idle** — off
**Shift indication works in ALL SI-Drive modes** (I / S / S#). SI-Drive only changes threshold aggressiveness:
- **I (Intelligent)**: earlier thresholds (encourages short-shifting for efficiency/learners)
- **S (Sport)**: standard thresholds
- **S# (Sport Sharp)**: later thresholds (hold gears longer)
Example — 2nd gear:
- I: shift indication at 4,000 RPM
- S: shift indication at 4,500 RPM
- S#: shift indication at 5,500 RPM
**Waveform gating by mute state:**
- Channel A (safety): always unmutable, waveform always renders during speech
- Channel B (conversational): muted by default at power-on; waveform only renders when unmuted AND speaking
- If Channel B muted → no speech, no waveform
### Audio layer — voice + tones
**Voice (single-shot, spoken once on threshold crossing):**
- Short, imperative, low-ambiguity: "Oil temp critical, reduce load"
- Consistent verb stems: "rising" (T1), "warning" (T2), "critical" (T3), "emergency" (T4)
- No pleasantries, no panic inflection (FAA guidance)
- TTS engine is KiSTI repo's choice, not specified here
**Tones (persistent while condition active, low cognitive load):**
- T2: single chime on threshold crossing, then silent
- T3: low-pitch pulse ~1 Hz, calm not panicked
- T4: double higher-pitch pulse ~0.5 Hz, insistent
- Silence = resolved (auto-clear when sensor drops below threshold)
### Voice channel architecture
**Channel A: Safety alerts**
- Always-on, always-audible
- Fires regardless of driving state or mute state
- Cannot be muted
- Triggered by sensor thresholds and ECU events only
**Channel B: Conversational AI (Claude)**
- Default state: **muted** on every power cycle
- Becomes available the moment driver presses unmute keypad button, regardless of driving state
- Stays available until re-mute or next power cycle
- Driver owns the decision — no state-based gating
### Complete delivery table
| Tier | Voice | Tone | Alarm LED | TFT | Shift lights |
|---|---|---|---|---|---|
| T0 Info | — | — | Dim color | Status area | Voice waveform or shift or idle |
| T1 Advisory | — | — | Solid color | Icon | Voice waveform or shift or idle |
| T2 Caution | Spoken once | Chime | Solid red | Banner | Red waveform during speech, then cede |
| T3 Warning | Spoken once | Low pulse ~1 Hz | Flashing red | Banner + flash | **Orange flash sweep, persistent** |
| T4 Emergency | Spoken once | Double pulse | Flashing red | Full-screen | **Red flash sweep, persistent** |
---
### Power-on self-check
All LEDs light for 2 seconds at power-on, then clear to nominal. Confirms hardware health before driving. OEM convention.
---
### 8-button keypad assignments (current)
| Button | Function | State behavior |
|---|---|---|
| 1 | Conversational voice mute/unmute | Toggle; default muted at power-on |
| 2 | MXG page forward | Momentary |
| 3 | MXG page back | Momentary |
| 4 | Lap trigger / session marker | Momentary |
| 5–8 | *Reserved* — TBD | — |
**ECU map selection** handled via OEM SI-Drive (I / S / S#), not keypad.
**Tire profile** handled via MXG menu, not keypad.
Candidates for reserved buttons 5–8 (decide after track sessions clarify what's missed):
- Launch control arm (momentary, hold-to-arm)
- Pit limiter toggle
- Data log start/stop override
- VDC / traction control disable
- Emergency "reduce all" (driver-triggered limp)
- Headlight flash / pass signal
---
### Configuration in RS3 (native MXG functionality)
All three visual layers configure in RaceStudio 3 — no custom firmware needed:
- **Shift lights:** standard shift config + alarm override conditions via math channels (any T3/T4 active)
- **Alarm LEDs:** one alarm per LED with threshold conditions, color, and flash frequency
- **TFT banners:** alarm text messages with priorities
KiSTI adds on top:
- Voice announcements (MXG doesn't speak)
- Cross-channel correlation (MXG does single-channel; KiSTI does compound)
- ONNX-detected learned anomalies (fire into same framework via CAN back to MXG)
- DuckDB logging of every alert event, state transition, and resolution
---
### Logging to DuckDB (every alert event)
- Timestamp
- Channel (oil_temp, coolant, knock, etc.)
- Severity tier
- Value at trigger
- Condition duration until resolution
- Session context (track / street / cold start / tire profile / SI-Drive position)
Feeds post-session review and long-term pattern detection.
---
### Implementation priority
1. **Now:** Oil temp (blue/green/off/red/flash) — simplest, highest value
2. **Next:** Coolant + oil pressure — same sensor infrastructure, proven thresholds
3. **Then:** Knock + lambda — ties to ECU tune work
4. **Later:** Cross-channel correlation logic — ML-assisted, after baseline sessions collected
5. **Ongoing:** Refine thresholds based on session data patterns (Racing Improves Breed)
---
## Item 17 — Brake sensor integration
Front and rear brake pressure sensors are installed on the car. Data acquisition only — no ABS recalibration needed until/unless brake hardware is upgraded.
**Current state:**
- Front brake pressure sensor: installed
- Rear brake pressure sensor: installed
- AP Racing brake kit: **on hold indefinitely** (moved to Future Items)
**Integration scope:**
- Route brake pressure sensors to Link G5 analog inputs (or Jetson direct if G5 inputs are full)
- Log to DuckDB at 50 Hz (per Item 7)
- Display on MXG diagnostic page (Item 12)
- Feed braking behavior into KiSTI session analysis (trail braking patterns, brake balance, threshold braking)
**Analysis targets (post-session):**
- Brake balance front/rear under different conditions
- Max brake pressure per corner per session (track use)
- Braking consistency lap-to-lap (fatigue indicator)
- Threshold braking proximity (how close to lockup on each stop)
**Cross-references:**
- Item 7 (data acquisition — adds 2 channels)
- Item 12 (dash display)
- Future Items (AP Racing kit, if/when resumed)
---
## Item 18 — Body CAN / indicator channel integration
Required to drive turn signals, high/low beam indicators, and fuel-level warnings on the MXG dash and in KiSTI alerts. **Currently BLOCKED** — these channels do not exist in the MXG's CAN stream today. Discovered 2026-04-18 during MXG alarm configuration session.

**Channels needed:**
- Turn signal LEFT (boolean, true = active)
- Turn signal RIGHT (boolean, true = active)
- High beam active (boolean)
- Low beam active (boolean)
- Fuel level (percent or litres — derive `FUEL_LOW` boolean from this)

**Source options** (decide per channel; can mix):
1. **Subaru body CAN** — body ECU broadcasts these natively. Requires tapping body CAN into the MXG's second CAN input (CAN2 on Strada) + DBC decoding. Richest source but most complex wiring.
2. **Physical wire taps → MXG digital inputs** — splice the blinker/headlight feed wires into MXG digital inputs. Simpler, but fuel level isn't a boolean so it needs an analog input.
3. **Physical wire taps → Link G5 inputs → Link CAN broadcast** — Link reads the wires and broadcasts on its existing CAN stream, MXG picks up from CAN1 alongside engine data. Cleanest architecturally (one DBC to maintain). Fuel level via existing Link analog input from the fuel sender.

**Recommended:** **Option 3** for turn signals and beams (Link wire taps → CAN broadcast). Fuel level via existing Link analog input.

**Blocks:**
- MXG alarm/indicator LEDs: LED 1 (left turn), LED 5 (right turn), LED slot TBD (high beam / low beam / fuel low)
- TFT display icons for same
- KiSTI voice announcements (e.g., "fuel low" on range calculation)
- DuckDB logging of driver inputs (turn signals useful for driving-style analysis)

**Cross-references:**
- Item 7 (data acquisition) — channels extend the channel inventory table
- Item 12 (dash integration) — MXG side consumes these
- Item 16 (alert framework) — fuel low fires as T1/T2 advisory; turn signals are T0 info only
- Item 11 (fault handling) — stock Subaru DTCs for body electrical are on this bus

---
## Future Items (on hold, deferred, or awaiting trigger)
### AP Racing brake kit (on hold indefinitely)
- CP9668/372mm front BBK considered at $5,000 CAD used
- Decision: on hold indefinitely — stock Brembo 4-pots adequate for current mission
- **If resumed:** ABS recalibration required for new pad friction coefficient, master cylinder pressure mapping, rear brake balance adjustment
- Brake pressure sensors (Item 17) already installed — would provide baseline data for pre/post BBK comparison
### Chassis-side items (not yet scoped)
- Alignment specs per use case (street / track / winter)
- Suspension damping modes (if adjustable dampers fitted)
- Aero (splitter, wing, underbody) — performance + cooling implications
- May warrant a separate "STI Chassis Task List" KB once items accumulate
### Keypad button 5–8 final assignments
- Defer until track sessions clarify which functions are most missed from physical controls
- Candidates listed in Item 16 keypad section
---
## Global cross-references
- KiSTI anomaly detection roadmap (Item 8) — feeds on all ECU channels, outputs elevated alerts via Item 16 framework
- RS3 overlay work (cfg_20260401_152932) — all dash visuals configured here
- Rogers Pass field mission (May 2026) — first real deployment test of Items 14, 15, 16 in field conditions
- Hardware chain: Link G5 → Korlan USB2CAN → Jetson Orin Nano → MXG 1.3 Strada (CAN return)
- KiSTI CAN setup: Zeus memory `db021919-0623-4bd3-bed2-dbb5f070877a`
