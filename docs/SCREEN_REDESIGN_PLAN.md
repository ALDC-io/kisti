# KiSTI Screen Redesign — Full Sensor Utilization Plan

**Date**: 2026-04-04 | **Author**: Claude Opus 4.6 (research + design)
**Status**: RESEARCH COMPLETE, DESIGN PROPOSED — awaiting JK approval

---

## Part 1: Research Synthesis

Six parallel research agents investigated 9 topics. Here are the consolidated findings that drive the design.

### Finding 1: Dark Cockpit is Non-Negotiable

Every professional system — AiM, MoTeC, F1 steering wheel displays — follows the same principle: **show nothing when everything is normal**. Research (Wickens 2002, Patten 2006) confirms that 3+ simultaneously visible data elements measurably degrade driving performance under high workload.

**Rule**: During dynamic driving, the display should present ONE dominant visual element. Supporting data exists in peripheral zones but must not compete for attention. A blank screen says "you're doing fine."

### Finding 2: The G-Circle Gap is Real (and Validated)

AiM logs all 9-axis IMU data from the GPS09 but provides **ZERO real-time body dynamics visualization** on the driver display. G-G diagrams exist only in Race Studio 3 post-session. MoTeC is the one exception — their C125/C127 (same 800x480) shows a simple G-circle with dot indicator. This validates KiSTI's approach: the G-circle works at 800x480, and it's the exact gap AiM leaves open.

**The correct shape is a friction ellipse** (not circle). The STI has asymmetric grip: ~1.0g lateral, ~1.2g braking, ~0.6-0.8g acceleration. Trail length: 0.5-1.0 seconds (10-20 dots at 20Hz). A subtle filled ellipse at 90% capability provides "how much grip am I using" context.

### Finding 3: Understeer Detection Works — But as Trend, Not Instant

Drivers cannot react to an instantaneous understeer indicator — proprioceptive feedback (seat of the pants) is 200-300ms faster than visual processing. However, **trend indicators** are genuinely useful: "you've been consistently understeering for the last few corners" reveals tire degradation or unconscious compensation the driver misses through feel alone.

**Primary method**: Bicycle model (steering angle + speed → expected yaw rate vs gyro Z). Instantaneous, no GPS dependency, works at 50Hz. Thresholds use ratio (actual/expected): neutral = 0.97-1.03, understeer < 0.90, oversteer > 1.10.

**Visualization**: Horizontal centered bar, green/yellow/red. Subtle, peripheral. Or: background tint on the G-ellipse itself (most information-dense, least cognitive load).

### Finding 4: Brake Quality = Longitudinal G, Not Pitch Rate

Professional systems use **longitudinal G (deceleration)** as the core braking metric. Pitch rate is a consequence of braking force through suspension geometry — it varies with setup changes. Two identical braking events produce different pitch rates if springs change. Longitudinal G stays the same.

**Pitch rate IS useful** as a suspension quality indicator and weight transfer rate metric — but for post-session analysis, not real-time display.

**Best visualization**: Vertical bar with peak hold (like a VU meter) and color zones: gray (light), yellow (moderate), green (threshold/optimal), red (ABS/lockup). Peak hold line fades after 2 seconds.

### Finding 5: Traction Loss = Slip Ratio vs GPS Ground Truth

Compare individual wheel speeds to GPS speed (ground truth). Slip ratio > 10% = advisory, > 20% = warning. For AWD with DCCD, use GPS as ground truth to avoid DCCD interpretation complexity. Show as front/rear grip bars **alongside DCCD** — unified drivetrain cluster showing input (lock %) vs output (grip %).

### Finding 6: Density Altitude is Not Useful Real-Time

For a turbo car, the ECU's MAP sensor continuously compensates for altitude. Density altitude tells the driver what the ECU already knows. No rally or hillclimb system shows DA in real-time. Boost pressure IS the turbo driver's density altitude. Show simple GPS altitude on Intelligent mode only — ambient information, not performance data.

### Finding 7: Corner Classification and Sector G-Profiling are Post-Session

No production or racing data system displays "fast right" or "slow hairpin" labels in real-time. The driver knows what corner they're in. Corner radius auto-categorization is valuable for post-session analysis. Sector G-force overlays are firmly post-session — the driver cannot interpret a G-trace graph at speed. **Sector time delta is the gold standard. Keep it.**

One addition worth considering: a small color-coded dot per sector showing peak braking G quality (did you brake as hard as your best lap?). This diagnoses confidence/fatigue fade.

### Finding 8: Coach, Not Dashboard

The gap between "data display" and "making the driver better" is bridged by **context and prescription**:

| Level | Example | Value at Speed |
|-------|---------|---------------|
| Raw data | "Lateral G: 0.85g" | Zero |
| Contextualized | "0.85g (best: 0.92g)" | Low |
| Interpreted | "Under-driving by 7%" | Medium |
| Coaching | "Carry more speed mid-corner" | High |
| Anticipatory | *[approaching corner]* "More speed" | Highest |

The delta timer (am I gaining or losing?) is the #1 proven real-time tool across Garmin Catalyst, AiM Solo 2, and F1. It works because it answers the only question that matters: "Am I faster or slower than before?"

**Audio beats visual** for in-corner feedback. One coaching focus per session (deliberate practice). Post-session debrief is where technique actually improves.

### Finding 9: What Professional Coaches Actually Look For

The 5 technique elements that separate fast from slow (in order of impact):

1. **Brake point consistency** — same point every lap, not how late
2. **Trail braking / brake release** — progressive release vs binary on/off
3. **Throttle application** — progressive roll-on vs snap
4. **Minimum corner speed** — commitment through mid-corner
5. **Smoothness** — steering/throttle/brake rate of change (jerk)

The coaching system should target ONE of these per session. The current `TechniqueAnalyzer` only uses lateral G for trail braking. The redesign adds longitudinal G analysis and feeds IMU data into all 5 categories.

---

## Part 2: Design Principles (Derived from Research)

1. **Dark cockpit**: Normal = invisible. Only abnormal states demand attention
2. **One hero at a time**: Each mode has one dominant element. Everything else is peripheral
3. **Color > numbers**: Pre-attentive color processing (~150ms) beats numeric reading (~500ms)
4. **Friction ellipse**: Proper asymmetric shape for G visualization
5. **Trend, not instant**: Understeer/oversteer shown as rolling trend, not per-frame
6. **Drivetrain cluster**: DCCD + front grip + rear grip as unified input/output display
7. **Coach, not dashboard**: Prescriptive text, not raw metrics
8. **Audio for corners**: Visual for straights, audio for in-corner cues
9. **Delta is king**: Time delta to reference is the #1 real-time tool
10. **Log everything, display little**: Full 20Hz logging feeds post-session analysis

---

## Part 3: Screen Designs

### What Stays on AiM Strada (NEVER put on KiSTI)

- RPM (sweep gauge + 10 RGB shift LEDs)
- Boost pressure (gauge)
- Speed (large numeric)
- Gear position (large numeric)
- Lambda/AFR (numeric)
- Oil pressure, oil temp, coolant temp (numerics + warnings)
- Fuel pressure, battery voltage (numerics)
- Basic lap timer (GPS09-driven)
- Track map with position dot (GPS09-driven)

---

### Screen 1: INTELLIGENT MODE — "What are the conditions?"

**Hero element**: FLIR thermal image (road awareness)
**Personality**: Guide/Explorer. Full info, weather, coaching, voice interaction.
**When**: Cruising, learning, parked reviewing data. Driver has time to look.

```
┌────────────────────────── 800 x 480 ──────────────────────────┐
│                                                                │
│  WEATHER      ROAD         HUMIDITY     BARO         [WARMING] │
│  12.4°        8.2°         67%          1013 hPa               │ y=0
│  AIR TEMP     ROAD SURFACE RELATIVE     BARO                   │
│                                                                │ y=110
├────────────────────────────────────────────────────────────────┤
│                                                                │
│               FLIR INFRARED IMAGE                              │
│               (full width inferno colormap)                    │ y=114
│               or "FLIR NOT CONNECTED"                          │
│                                                                │
│                                                                │ y=306
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  [==L==][==C==][==R==] DRY    │  ELEV 847 m   ◉ 0.12g        │ y=310
│                               │  GPS ●12 3D                   │
│  SLIP Δ +0.3   DCCD ████ 35% │                ╭──╮           │ y=346
│  ABS○  VDC○                   │               │● │  mini     │
│                               │                ╰──╯  G-dot   │ y=396
├────────────────────────────────────────────────────────────────┤
│  ▸ Smooth braking — road surface optimal                       │ y=400
│  ▹ "The road is dry and 8 degrees..."                          │ y=420
│  ▹ "Good morning. Engine warming."                             │ y=436
│                                                                │ y=455
├────────────────────────────────────────────────────────────────┤
│  Coaching: conditions text (sentiment-colored)                 │ y=458..480
└────────────────────────────────────────────────────────────────┘
```

#### Element Specification

| Element | Position | Size | Data Source | Color Logic | Stale Behavior |
|---------|----------|------|-------------|-------------|----------------|
| Weather card | y=0..110, full width | 4 columns | `ambient_*` from Yoctopuce | White text, MODE_I_ACCENT headers | "---" gray when `ambient_available=false` |
| FLIR image | y=114..306, full width | 800x192 | FLIR Lepton USB | Inferno colormap via CLAHE | "FLIR NOT CONNECTED" gray text |
| Warm-up badge | y=118, right | 160x24 pill | `warmup_state` | Blue/cherry/green per state | Hidden when no engine data |
| Zone bar (L/C/R) | y=314, x=10..300 | 290x40 | `surface_state_*` | Per-zone color, urgency alpha | All DRY (green, dim) |
| Worst label | y=356, x=10..300 | 290x16 | `worst_state_label()` | Worst zone color | "DRY" dim green |
| Slip delta | y=370, x=10 | 160x24 | `slip_delta` | Cyan/yellow/red by magnitude | "---" gray |
| DCCD bar | y=370, x=180 | 120x20 | `dccd_command_pct` | Blue fill, yellow >80% | "---" gray |
| ABS/VDC dots | y=394, x=10 | 80x18 | `abs_active`, `vdc_tc` | Red/yellow when active, DIM normally | DIM dots |
| **GPS altitude** | y=314, x=520 | 150x20 | `gps_altitude_m` | White text, GRAY label | "---" when GPS stale |
| **GPS status** | y=338, x=520 | 150x20 | `gps_satellites`, `gps_fix_quality` | Green dot + count when lock, gray when stale | "NO GPS" gray |
| **Mini G-dot** | y=346, x=680 | 80x80 circle | `imu_accel_x`, `imu_accel_y` | Cyan dot on DIM circle, white magnitude | Dot at center, "---" |
| **G magnitude** | y=314, x=680 | 80x20 | `sqrt(x²+y²)` | White, 1 decimal | "---" gray |
| Voice ticker | y=400..455, x=20 | 380x55 | Voice pipeline | Fading alpha (120/70/40) | Empty |
| Coaching bar | y=458..480 | Full width | `ConditionRuleEngine` | Green/amber/gray | Empty |

#### New GPS09/IMU Elements (not in current screen)
- **GPS altitude**: Simple elevation readout. Useful on mountain passes (Rogers Pass, Sea-to-Sky). Ambient information.
- **GPS satellite count + fix quality**: Confirms sensor health at a glance. Green dot = 3D fix. Gray = degraded.
- **Mini G-dot gauge**: 80px diameter circle with current G dot. Ambient body dynamics — shows if the car is being pushed, even in cruise mode. Combined G magnitude below.

#### What Was Removed
- Nothing removed. Intelligent mode is information-rich by design. Elements were rearranged to accommodate GPS/IMU additions in the right column of the status section.

#### How It Makes the Driver Better
- GPS altitude provides elevation awareness on mountain passes (turbo lag expectations, brake cooling on descents)
- GPS status confirms the timing/track system is receiving position data before the driver switches to Sport/Sport Sharp
- Mini G-gauge builds body dynamics awareness even in cruise mode — the driver learns to associate steering inputs with G-force feedback
- All new elements are ambient/educational — appropriate for the "Guide" personality

#### Dark Cockpit Behavior
- Zone bars: DRY zones are alpha=100 (barely visible). Escalates through WET/COLD/LOW_GRIP
- ABS/VDC: DIM gray dots when inactive. Bright red/yellow only when active
- DCCD: Blue fill only, no attention-grabbing colors unless >80% lock
- Mini G-dot: Faint circle rings, dot moves subtly. Only draws attention with high-G events
- Edge glow: Pulsing red border only for LOW_GRIP zones

---

### Screen 2: SPORT MODE — "What do I need to know right now?"

**Hero element**: G-force friction ellipse (driving dynamics)
**Personality**: Co-Driver. Focused on dynamics, technique, conditions. No fluff.
**When**: Spirited driving, canyon runs, fast road. Eyes mostly on road.

```
┌────────────────────────── 800 x 480 ──────────────────────────┐
│                                                                │
│  DCCD ████████░░ 80%   ABS○ VDC○  │  [=L=][=C=][=R=]  DRY   │ y=0
│  F ██████████████ 98%  GRIP       │                           │
│  R █████████░░░░  71%  GRIP       │  SLIP Δ +0.3 km/h        │ y=74
├───────────────────────────────────┴───────────────────────────┤
│                                   │                           │
│  BRAKE G                          │          BRAKE            │ y=78
│  ████████░░░  [-0.85g]            │            │              │
│  ──────── peak hold               │            │              │
│                                   │       L ───┼─── R         │
│  BALANCE                          │            │              │
│  [========|●===]  slight US       │          ACCEL            │
│                                   │                           │ y=130
│  TRAIL BRAKE                      │     ╭─── envelope ───╮   │
│  ██████░░░░  62%                  │     │    ···trail     │   │
│                                   │     │      ● dot      │   │
│  STEER                            │     ╰────────────────╯   │
│  [════════|═══]  -142°            │                           │
│                                   │         0.85g             │ y=396
│                                   │                           │
├────────────────────────────────────────────────────────────────┤
│  Good trail braking — carry more speed mid-corner              │ y=400
├────────────────────────────────────────────────────────────────┤
│  ▹ "Corner exit looks clean"      │                           │ y=424
│  ▹ "Surface temperature dropping" │                           │
│                                                                │ y=460
├────────────────────────────────────────────────────────────────┤
│  Coaching bar (sentiment-colored, full width)                  │ y=462..480
└────────────────────────────────────────────────────────────────┘
```

#### Element Specification

| Element | Position | Size | Data Source | Color Logic | Stale Behavior |
|---------|----------|------|-------------|-------------|----------------|
| **Drivetrain cluster** | y=0..74, x=0..420 | 420x74 | See sub-elements | — | — |
| DCCD bar | y=4, x=8..340 | 280x22 + pct text | `dccd_command_pct` | Green <40%, yellow 40-70%, red >70% | "---" gray bar |
| **Front grip bar** | y=30, x=8..180 | 170x18 | `slip_ratio(wheel_fl,fr, gps_speed)` | Green >80%, yellow 60-80%, red <60% | Hidden when no GPS |
| **Rear grip bar** | y=52, x=8..180 | 170x18 | `slip_ratio(wheel_rl,rr, gps_speed)` | Green >80%, yellow 60-80%, red <60% | Hidden when no GPS |
| ABS/VDC indicators | y=30, x=200 | 80x18 | `abs_active`, `vdc_tc` | DIM normally, red/yellow active | DIM |
| "GRIP" label | y=30, x=190 | 40x40 | — | GRAY label | — |
| Road condition bar | y=4..70, x=440..790 | 350x66 | `surface_state_*` | Per-zone urgency alpha | DRY (dim) |
| Slip delta | y=52, x=440 | 160x18 | `slip_delta` | Cyan/yellow/red | "---" gray |
| **Brake G bar** | y=96..164, x=8..200 | 200x28 bar | `imu_accel_x` (negated) | Gray 0-0.3g, yellow 0.3-0.7g, green 0.7-1.0g, red >1.0g | Gray empty bar |
| **Brake G peak hold** | y=96..164, x=8..200 | 2px line | Peak of `imu_accel_x` per brake event | White line, fades after 2s | Hidden |
| Brake G value | y=96, x=210 | 80x28 | `-imu_accel_x` | Match bar color | "---" |
| **Balance bar** | y=182..210, x=8..300 | 300x28 centered | `actual_yaw / expected_yaw` ratio | Green center, yellow mild, red severe | Center position (neutral) |
| Balance label | y=182, x=310 | 100x16 | Classify balance | "neutral"/"slight US"/"OS" | "---" |
| **Trail brake %** | y=230..258, x=8..200 | 200x28 | Brake+steer overlap ratio | Green >30%, dim <10% | "---" gray |
| Steer bar | y=278..306, x=8..300 | 300x28 centered | `steering_angle` | CYAN fill from center | Center (zero) |
| **G-force ellipse** | y=78..396, x=380..790 | 280x318 area, 140px radius | `imu_accel_x`, `imu_accel_y` | — | Dot at center |
| Ellipse envelope | — | 90% of capability | Tuned from data | 12% alpha fill, 30% border | Same (reference stays) |
| Ellipse trail | — | 20 dots (1.0s) | Ring buffer | Fading cyan/orange (by G%) | Empty |
| Ellipse dot | — | 6px radius | Current G | Green <60%, yellow 60-85%, red >85% of envelope | Center dot |
| **Ellipse US/OS tint** | — | Full circle background | Balance ratio | None=neutral, blue tint=US, red tint=OS | None |
| G magnitude | y=370, x=540 | 120x28 | `sqrt(x²+y²)` | White, 1 decimal | "---" |
| Coaching text | y=400..420, full width | 800x20 | `TechniqueAnalyzer` | Green/amber/gray sentiment | Empty (hidden) |
| Voice ticker | y=424..460, x=20 | 380x36 | Voice pipeline | Fading alpha | Empty |
| Coaching bar | y=462..480, full width | 800x18 | Coaching system | Sentiment color | Empty |

#### New GPS09/IMU Elements (not in current screen)

| New Element | Replaces | Data Source | Why |
|-------------|----------|-------------|-----|
| **Friction ellipse** (envelope + trail + colored dot) | Simple G-circle (dot + rings only) | `imu_accel_x`, `imu_accel_y` | Shows grip utilization %, not just position. Envelope = "how much grip is available." Color = "how hard am I pushing." |
| **Ellipse understeer tint** | Nothing | `imu_gyro_z` vs bicycle model expected yaw | Background shifts blue (US) or red (OS). Zero cognitive load — driver sees G-circle change mood. |
| **Brake G bar with peak hold** | Brake pressure bar | `imu_accel_x` (longitudinal G) | Brake pressure shows pedal effort. Brake G shows actual deceleration. Coaches care about G, not pressure. Peak hold shows "did I reach threshold braking?" |
| **Balance bar** (understeer/oversteer) | Yaw rate bar | `imu_gyro_z` vs `expected_yaw(speed, steer)` | Raw yaw rate is meaningless without context. Balance ratio contextualizes it: "am I rotating as expected?" |
| **Trail brake % bar** | Nothing (was coaching text only) | Brake pressure + steering overlap | Visualizes the #2 technique gap. Driver sees in real-time whether they're trail braking. |
| **Front/rear grip bars** | Nothing | Wheel speeds vs `gps_speed_mps` | Shows traction state per axle. Paired with DCCD = cause and effect. |

#### What Was Removed

| Removed | Why |
|---------|-----|
| Lateral G bar | Redundant — the G-ellipse shows lateral G directly as horizontal dot position |
| Raw brake pressure bar | Replaced by brake G bar (measures outcome, not input) |
| Raw yaw rate bar | Replaced by balance bar (contextualizes yaw against expected yaw) |

#### How It Makes the Driver Better

1. **Friction ellipse with envelope**: Driver sees "I'm only using 60% of available grip" — builds confidence to push harder. The envelope is the target, the dot is reality. Close the gap.
2. **Brake G peak hold**: After each braking zone, the peak hold line shows "did I brake as hard as the car can?" If the line consistently falls short of the green zone (threshold), the coaching system says "brake harder."
3. **Balance bar**: If the bar consistently sits right-of-center (understeer), the driver knows the car is pushing — adjust DCCD, change line, or communicate to engineer for setup change.
4. **Trail brake %**: Direct visual feedback on THE most impactful technique gap for intermediate drivers. "I see the bar is low — I need to hold brakes deeper into the corner."
5. **Grip bars + DCCD cluster**: "My rear grip is dropping and DCCD is at 40% — I should increase lock." Input/output relationship visible at a glance.

#### Dark Cockpit Behavior

- **Brake G bar**: Gray and nearly invisible when not braking. Lights up only during braking events. Peak hold appears then fades.
- **Balance bar**: Centered green dot. Only draws attention when it deflects into yellow/red zones. During straight-line driving, it's invisible (no yaw expected, no yaw measured).
- **Trail brake %**: Only visible during brake+steer overlap events. Hidden during pure braking or pure cornering.
- **Grip bars**: Solid green (full grip) is intentionally dim. Only becomes bright when grip drops below 80%.
- **G-ellipse**: Trail dots are very faint. Envelope is barely visible. Only the current dot and magnitude draw the eye.
- **Understeer tint**: None (transparent) when balanced. Subtle tint only when ratio deviates beyond 0.90/1.10.

---

### Screen 3: SPORT SHARP MODE — "Am I faster? Am I safe?"

**Hero element**: Delta bar (time delta to reference lap)
**Personality**: Race Engineer. Absolute minimum visual noise. Every pixel earns its place.
**When**: Track day, maximum attack. Eyes on track 98% of the time.

```
┌────────────────────────── 800 x 480 ──────────────────────────┐
│                                                                │
│  [====================|████████████]    +1.234                 │ y=0
│   green=faster          red=slower                             │
│                                                                │ y=88
├────────────────────────────────────┬───────────────────────────┤
│                                    │                           │
│  LAP 7        Mission Raceway      │       BRAKE              │ y=92
│                                    │         │                │
│        01:42.837                   │    L ───●─── R           │
│                                    │         │                │
│  PRED  01:43.102                   │       ACCEL              │
│                                    │   ╭── envelope ──╮      │
│                                    │   │   ···trail   │      │
│  BEST  01:41.556                   │   │     ● dot    │      │
│  THEO  01:40.892                   │   ╰──────────────╯      │
│                                    │       0.92g              │ y=274
├────────────────────────────────────┴───────────────────────────┤
│                                                                │
│  [ S1: 28.4  ●] [ S2: 31.2  ○] [▐▌ S3      ] [   S4       ] │ y=278
│  [ faster -.3 ] [ close      ] [ active     ] [             ] │
│  [  green     ] [  white     ] [ pulse yllw ] [   dim       ] │
│                                                                │ y=368
├────────────────────────────────────────────────────────────────┤
│                                                                │
│     OIL            COOL           OIL T          GRIP         │ y=372
│                                                 [L][C][R]     │
│     72             91             108                         │
│     PSI            °C             °C            (zone bar)    │
│                                                                │ y=456
├────────────────────────────────────────────────────────────────┤
│  ▹ voice ticker (2 lines max, dim)                             │ y=458..480
└────────────────────────────────────────────────────────────────┘
```

#### Element Specification

| Element | Position | Size | Data Source | Color Logic | Stale Behavior |
|---------|----------|------|-------------|-------------|----------------|
| Delta bar | y=0..88, x=10..790 | 780x70 bar | `timing.delta_ms` | Green fill left (faster), red fill right (slower) | "NO TIMING" gray text |
| Delta text | Centered in bar | 36pt bold | `timing.delta_ms` | Green <0, red >0, white =0 | "---" |
| Timing panel | y=92..274, x=0..480 | 480x182 | `timing.*` | — | "---" values |
| Lap label | y=96, x=20 | 120x24 | `timing.lap_count` | GRAY | "LAP --" |
| Track name | y=96, x=150 | 300x24 | `timing.track_name` | DIM | Empty |
| Current lap time | y=122, centered in left | 48pt Courier bold | `timing.current_lap_time_ms` | WHITE | "--:--.---" |
| Predicted lap | y=194, centered in left | 26pt Courier bold | `timing.predicted_lap_ms` | GRAY | Hidden if 0 |
| Best lap | y=232, x=20 | 300x20 | `timing.best_lap_ms` | DIM | Hidden if 0 |
| Theoretical best | y=252, x=20 | 300x20 | `timing.theoretical_best_ms` | DIM | Hidden if 0 |
| **G-force ellipse** | y=92..274, x=480..800 | 320x182 area, 80px radius | `imu_accel_x`, `imu_accel_y` | — | Dot at center |
| Ellipse envelope | — | 90% capability | Tuned from data | 10% alpha fill | Same |
| Ellipse trail | — | 10 dots (0.5s) | Ring buffer | Fading MODE_SS_ACCENT | Empty |
| Ellipse dot | — | 4px radius | Current G | Green/yellow/red by G% | Center |
| **Ellipse US/OS tint** | — | Background | Balance ratio | None/blue(US)/red(OS), subtle | None |
| G magnitude | y=252, x=590 | 100x24 | `sqrt(x²+y²)` | WHITE, 1 decimal | "---" |
| Sector strip | y=278..368, x=10..790 | 780x90 | `timing.sector_*` | Green=beat best, red=slower | Black placeholders |
| Sector time | Centered in each block | 18pt bold | `sector_times[i]` | WHITE on green/red | "S1" dim label |
| Sector insight | Below time | 11pt | `_sector_insight()` | Context color | Empty |
| Sector delta | Bottom of block | 10pt | `sector - best_sector` | WHITE 80% alpha | Empty |
| **Sector brake dot** | Top-right of block | 8px circle | Peak `abs(imu_accel_x)` per sector | Green ≥ best, yellow within 10%, red >10% off | Hidden |
| Safety vitals | y=372..456, x=0..800 | 4 zones, 200px each | See sub-elements | — | — |
| OIL vital | x=0..200 | 200x84 | `oil_psi` | **DIM when normal** (15-70 PSI). Yellow ≤25. Red ≤15 | GRAY "---" |
| COOL vital | x=200..400 | 200x84 | `coolant_temp` | **DIM when normal** (<100°C). Yellow ≥100. Red ≥105 | GRAY "---" |
| OIL T vital | x=400..600 | 200x84 | `oil_temp_c` | **DIM when normal** (<130°C). Yellow ≥130. Red ≥140 | GRAY "---" |
| **GRIP vital** | x=600..800 | 200x84 | `surface_state_*` | 3-zone mini bar (L/C/R) with colors | DRY (dim green) |
| Voice ticker | y=458..480, x=20 | 380x22 | Voice pipeline | Fading alpha, 2 lines | Empty |

#### New GPS09/IMU Elements (not in current screen)

| New Element | Replaces | Data Source | Why |
|-------------|----------|-------------|-----|
| **Friction ellipse** (envelope + trail) | Simple G-circle | `imu_accel_*` | Shows grip utilization. Shorter trail (0.5s) than Sport — less visual noise for maximum attack |
| **Understeer tint** on G-ellipse | Nothing | `imu_gyro_z` vs bicycle model | Peripheral awareness of balance without adding a separate element. Saves pixels |
| **Sector brake quality dots** | Nothing | Peak `abs(imu_accel_x)` per sector vs best lap | Diagnoses braking confidence/fatigue fade. Green dot = "you braked as hard as your best." Red dot = "you left braking performance on the table." |
| **GRIP vital** (3-zone mini bar) | ROAD vital (single temp number) | `surface_state_*` | A single road temp number requires interpretation. A 3-zone color bar is instant: green/blue/cyan/red across left/center/right. Pre-attentive |

#### What Was Removed

| Removed | Why |
|---------|-----|
| ROAD vital (single temp °C) | Replaced by GRIP vital (3-zone color bar). Color > numbers. The temp number required mental thresholding. The color bar does it automatically |
| Nothing else | Sport Sharp is already minimal. Only upgrades, no removals |

#### How It Makes the Driver Better

1. **Delta bar remains hero**: The proven #1 tool. Am I faster or slower? One glance, one answer.
2. **Sector brake quality dots**: After completing a sector, a small colored dot appears. Green = "I braked as hard as my best lap." Red = "I left braking on the table." Over a stint, if dots trend from green to red, the driver knows fatigue is setting in — time to pit or back off.
3. **G-ellipse with envelope**: During canyon driving without timing, this becomes the hero element. "Am I using the car's capability?" The envelope is the target.
4. **GRIP mini-bar**: Replace one temperature number with three colored blocks. The driver sees "right side is cold" instantly. No mental math needed.

#### Dark Cockpit Behavior (CRITICAL for this screen)

- **Safety vitals**: All labels and values are **DIM gray** when in normal range. Only the label and value light up (yellow/red) when a threshold is crossed. Currently they show WHITE values always — this wastes attention.
- **Sector strip**: Empty sectors are pure black with dim "S3" labels. Active sector has pulsing yellow border. Completed sectors flash green/red briefly then settle.
- **G-ellipse**: Envelope is barely visible (10% alpha). Trail is very short (0.5s). Minimal visual noise.
- **Delta bar**: When delta is near zero (±100ms), the fill is tiny and unobtrusive. Only large deltas (±1s+) fill significantly.
- **Voice ticker**: Maximum 2 lines, very dim. This screen is about driving, not reading.

---

## Part 4: Cross-Screen Consistency

### Road Condition (FLIR + Ambient) Across All 3 Screens

| Screen | Presentation | Alpha/Intensity |
|--------|-------------|-----------------|
| Intelligent | Full zone bar (290x40) with labels + worst label text + full FLIR IR image | High (alpha=28 tint, labels visible) |
| Sport | Zone bar (350x66) in top-right panel, no labels | Medium (alpha=18 tint) |
| Sport Sharp | Mini 3-zone bar in GRIP vital zone (200x40), no labels | Low (alpha=12 tint) |

**Consistent across all**: DRY zones are nearly invisible. Urgency escalates through WET → COLD → LOW_GRIP. Same color mapping (`SurfaceState.color`), same alpha scaling (`_TINT_SCALE`).

### Edge Glow Behavior

Identical across all 3 screens: 8px pulsing red inner border when ANY zone is LOW_GRIP. Alpha oscillates 40→90→40 at ~1Hz. This is the strongest pre-attentive feature — impossible to miss in peripheral vision.

No change from current implementation (`paint_edge_glow` in `road_condition.py`).

### Voice Ticker Placement

| Screen | Position | Lines | Width |
|--------|----------|-------|-------|
| Intelligent | y=400..455, x=20 | 3 lines | 380px |
| Sport | y=424..460, x=20 | 3 lines | 380px |
| Sport Sharp | y=458..480, x=20 | 2 lines | 380px |

**Consistent**: Always bottom-left. Fading alpha (120/70/40). Helvetica 10-11pt. Elided with `ElideRight`. Never competes with hero elements.

### Safety Vital Presentation

| Screen | Where | Style |
|--------|-------|-------|
| Intelligent | Status strip: ABS/VDC dots + DCCD bar + slip value | Dim indicators, bright on activation |
| Sport | Drivetrain cluster: DCCD + grip bars + ABS/VDC | Dim green bars, bright on grip loss |
| Sport Sharp | Bottom strip: OIL/COOL/OIL T/GRIP, 4 zones | **DIM until warning** — gray text/values when normal, yellow/red when threshold crossed |

**Consistent principle**: Normal = dim/invisible. Warning = bright. Critical = bright + edge glow.

---

## Part 5: New Analysis Functions Required

### 1. Understeer/Oversteer Calculator (`coaching/balance_analyzer.py`)

```python
def expected_yaw_rate(speed_mps: float, steer_angle_deg: float) -> float:
    """Bicycle model: expected yaw rate from steering input."""

def balance_ratio(actual_yaw: float, expected_yaw: float) -> float:
    """Ratio of actual to expected yaw rate. <0.97 = understeer, >1.03 = oversteer."""

def classify_balance(ratio: float) -> str:
    """'neutral' | 'understeer_mild' | 'understeer_severe' | 'oversteer_mild' | 'oversteer_severe'"""
```

**Tests**: Straight-line → neutral. Known radius + speed → expected ratio. Oversteer injection → correct classification. Speed gate below 30 km/h.

### 2. Brake Quality Analyzer (extend `coaching/technique_analyzer.py`)

```python
def brake_g_quality(accel_x_samples: list[float]) -> dict:
    """Analyze braking event: peak_g, rise_time_ms, release_linearity."""

def brake_event_detect(accel_x: float, threshold: float = 0.2) -> bool:
    """True when longitudinal G exceeds threshold (braking detected)."""
```

**Tests**: Smooth braking profile → high score. Panic braking → low score. No braking → no event.

### 3. Traction/Grip Calculator (`coaching/grip_analyzer.py`)

```python
def wheel_slip_ratio(wheel_speed_kph: float, gps_speed_mps: float) -> float:
    """Slip ratio: (wheel - ground) / ground. Positive = wheelspin, negative = lockup."""

def axle_grip_pct(front_slip: float, rear_slip: float) -> tuple[float, float]:
    """Front and rear grip percentage (100% = full grip, 0% = full slide)."""
```

**Tests**: Matching speeds → 0% slip, 100% grip. 10% slip → advisory threshold. Speed gate below 10 km/h.

### 4. Sector Brake Quality Tracker (extend `timing/timing_manager.py`)

```python
def record_sector_peak_brake_g(sector: int, peak_g: float) -> None:
    """Track peak braking G per sector for quality dots."""

def sector_brake_quality(sector: int) -> str:
    """'good' | 'fair' | 'weak' based on peak G vs best lap's peak G for this sector."""
```

### 5. Trail Brake Ratio (extend `coaching/technique_analyzer.py`)

```python
def trail_brake_ratio(brake_active: bool, steer_active: bool) -> float:
    """Rolling ratio of brake+steer overlap samples to total braking samples."""
```

---

## Part 6: Sensor Utilization After Redesign

| Channel | Current Use | After Redesign |
|---------|-------------|----------------|
| Lateral G (Y) | G-circle, bar, coaching | Friction ellipse (colored dot + trail + envelope), coaching |
| **Longitudinal G (X)** | G-circle only | Friction ellipse + **brake G bar with peak hold** + **sector brake quality dots** + coaching |
| **Vertical G (Z)** | Logged only | Logged only (post-session road surface quality analysis) |
| **Gyro X (Roll)** | Logged only | Logged only (post-session suspension analysis) |
| **Gyro Y (Pitch)** | Logged only | Logged only (post-session brake/suspension analysis) |
| **Gyro Z (Yaw)** | Sport bar only | **Balance analyzer** (understeer/oversteer via bicycle model) + G-ellipse tint |
| **GPS Lat/Lon** | Sector crossing | Sector crossing (unchanged) |
| **GPS Speed** | Logged only | **Traction/grip analyzer** (ground truth for slip ratio) + **balance analyzer** (speed input to bicycle model) |
| **GPS Heading** | Track bearing | Track bearing + **secondary validation for balance analyzer** |
| **GPS Altitude** | Logged only | **Intelligent screen display** (elevation readout) |
| **GPS Satellites** | GPS loss alert | GPS loss alert + **Intelligent screen status** (satellite count + fix quality) |
| GPS Fix Quality | Logged only | **Intelligent screen status** |

**Assessment: ~75% of sensor capability now used in real-time analysis** (up from ~25%).

Remaining 25% intentionally post-session only:
- Vertical G (Z): road surface quality profiling
- Gyro X (Roll): suspension dynamics, weight transfer rate
- Gyro Y (Pitch): brake suspension response, ride quality
- These are engineering channels — useful for setup decisions in Race Studio / DuckDB analysis, not for the driver at speed.

---

## Part 7: Implementation Order

### Phase 1: Analysis Functions (no UI changes)
1. `coaching/balance_analyzer.py` — understeer/oversteer calculator
2. `coaching/grip_analyzer.py` — traction/slip ratio calculator
3. Extend `coaching/technique_analyzer.py` — add brake G quality, trail brake ratio
4. Tests for all new analyzers

### Phase 2: G-Force Ellipse Upgrade (shared component)
1. New `ui/g_force_ellipse.py` — friction ellipse with envelope, trail, colored dot, US/OS tint
2. Replace G-circle in `sport_screen.py` with new ellipse widget
3. Replace G-circle in `sharp_screen.py` with new ellipse widget (smaller, shorter trail)
4. Tests for ellipse rendering logic

### Phase 3: Sport Screen Redesign
1. Add drivetrain cluster (DCCD + front/rear grip bars)
2. Replace lateral G bar, brake pressure bar, yaw bar with brake G, balance, trail %
3. Integrate coaching text improvements
4. Dark cockpit behavior for all new elements

### Phase 4: Sport Sharp Screen Redesign
1. Add sector brake quality dots
2. Replace ROAD vital with GRIP mini-bar
3. Dark cockpit safety vitals (dim until warning)
4. Voice ticker reduction (2 lines max)

### Phase 5: Intelligent Screen Additions
1. Add GPS altitude, satellite count, fix quality
2. Add mini G-dot gauge
3. Rearrange status section layout

### Phase 6: Coaching System Upgrade
1. Feed longitudinal G, gyro Z, GPS speed into `TechniqueAnalyzer`
2. Add brake quality coaching prompts
3. Add balance trend coaching prompts
4. Add grip coaching prompts (DCCD recommendations)
