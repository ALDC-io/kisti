# AiM MXG Strada — SI-Drive Mode-Aware Shift Light Investigation

**Date**: 2026-04-01
**Hardware**: AiM Strada 7" Street Edition + Link G5 Neo 4 ECU
**CAN Bus**: 1 Mbps, shared bus (Link ECU, AiM Strada, Jetson/KiSTI)

## Problem Statement

KiSTI uses the SI-Drive physical knob (CAN frame 0x6B0) to switch between three driving modes:
- **Intelligent** (0) — calm/diagnostic
- **Sport** (1) — performance
- **Sport Sharp** (2) — track attack

Each mode has different RPM characteristics. Shift lights on the MXG Strada should reflect this:
- Intelligent: no shift lights (street driving, no redline approaches)
- Sport: shift at ~5,500 RPM (spirited driving, current tune is 350 WHP)
- Sport Sharp: shift at ~6,800 RPM (track, squeeze every rev)

## Key Finding: AiM Shift LEDs Are NOT CAN-Addressable

From `can/can_config.py` line 380-385:

> AiM MXG Strada shift lights are NOT directly addressable via CAN.
> AiM uses internal firmware thresholds configured in Race Studio 3.

The LED waveform frames (0x6C0-0x6C1) drive a **separate** external controller (Arduino/ESP32) for the KiSTI voice waveform visualizer. These are independent of the AiM dash shift LEDs.

## CAN Bus Architecture

```
Link G5 Neo 4 (ECU)
  ├── 0x360-0x362  Generic Dash (RPM, boost, coolant, oil temp, etc.) @ 50 Hz
  ├── 0x6A0-0x6A3  KiSTI custom frames (DCCD, wheel speed, dynamics) @ 50 Hz
  ├── 0x6B0        SI-Drive mode (0/1/2) @ 10 Hz
  ├── 0x6B1        Extended sensors (MAP 4-bar, IAT, ethanol, oil PSI) @ 20 Hz
  └── 0x6B2        Keypad state (on-change)

AiM GPS09 Pro (via Strada CAN)
  ├── 0x6A4-0x6A5  GPS position + extended @ 10 Hz
  └── 0x6A6-0x6A7  IMU accel + gyro @ 50 Hz

Jetson (KiSTI) — Output
  └── 0x6C0-0x6C1  LED waveform (external controller) @ 30 Hz

All devices share the same 1 Mbps CAN bus.
AiM Strada sees ALL frames including 0x6B0 (SI-Drive).
```

## Solution: RS3 Math Channels + Conditional Shift Thresholds

The AiM MXG Strada can receive **any** CAN frame on the bus. In Race Studio 3:

### Step 1: Define CAN Channel for SI-Drive Mode

Create a custom CAN channel in RS3:
- **Name**: `SI_Drive_Mode`
- **CAN ID**: `0x6B0`
- **Byte offset**: 0
- **Length**: 1 byte (uint8)
- **Values**: 0 = Intelligent, 1 = Sport, 2 = Sport Sharp

### Step 2: Create Math Channels for Shift Thresholds

RS3 supports math channels with conditional logic:

```
// ShiftPoint — dynamic RPM threshold based on SI-Drive mode
ShiftPoint = 
  if(SI_Drive_Mode == 0, 0,           // Intelligent: disabled (0 = never trigger)
  if(SI_Drive_Mode == 1, 5500,        // Sport: 5,500 RPM
  if(SI_Drive_Mode == 2, 6800,        // Sport Sharp: 6,800 RPM
  0)))                                 // Fallback: disabled

// ShiftWarning — 500 RPM before shift point (amber zone)
ShiftWarning = 
  if(ShiftPoint > 0, ShiftPoint - 500, 0)
```

### Step 3: Configure Shift Light Thresholds

In RS3 shift light configuration:
- **Channel**: Use `ShiftWarning` and `ShiftPoint` math channels (NOT raw RPM)
- **Amber LEDs (outer)**: Activate when RPM >= `ShiftWarning`
- **Red LEDs (inner)**: Activate when RPM >= `ShiftPoint`
- **Flash**: All LEDs flash when RPM >= `ShiftPoint + 200` (over-rev warning)

### Step 4: Alternative — Direct RPM with Mode-Aware Pages

If RS3 doesn't support math channels in shift light config (some firmware versions), use:
- **3 display pages** on the MXG, one per SI-Drive mode
- Each page has its own shift light threshold tied to raw RPM
- SI-Drive CAN channel (0x6B0) triggers automatic page switching

## AiM CAN Receive Configuration

In RS3 CAN bus setup:
- **Bus speed**: 1,000 kbps (must match Link G5 config)
- **Protocol**: Raw CAN (not OBD-II, not Link-specific)
- Add custom CAN channels for any frame the Strada should interpret

Minimum channels to define:
| Channel | CAN ID | Offset | Size | Scale | Unit |
|---------|--------|--------|------|-------|------|
| SI_Drive_Mode | 0x6B0 | 0 | 1B | 1 | - |
| RPM | 0x360 | 0 | 2B | 1 | rpm |
| Boost_kPa | 0x360 | 4 | 2B | 0.1 | kPa |
| Coolant_C | 0x360 | 2 | 2B | 0.1 | C |

Note: Generic Dash byte order — Link's native Generic Dash uses LITTLE-endian, but our User CAN stream may use BIG-endian (see `can_config.py` line 183-185). **Verify byte order in PCLink G5 CAN stream configuration before configuring RS3.**

## SI-Drive OEM vs Link Remapping

Important: The OEM SI-Drive CAN values are:
- 1 = Sport Sharp
- 2 = Intelligent
- 3 = Sport

The Link G5 **remaps** these in User CAN to:
- 0 = Intelligent
- 1 = Sport
- 2 = Sport Sharp

RS3 must use the **remapped** values (0/1/2) from frame 0x6B0, not the OEM values.

## Pre-Tune Session Checklist (Aaron @ Boost Barn)

- [ ] Export RS3 config file before making changes (backup)
- [ ] Verify AiM Strada CAN bus speed is 1 Mbps in RS3
- [ ] Add SI_Drive_Mode as custom CAN channel (0x6B0, byte 0, uint8)
- [ ] Add RPM from Generic Dash if not already defined (0x360, bytes 0-1)
- [ ] Create ShiftPoint and ShiftWarning math channels
- [ ] Configure shift LEDs against math channels (or per-page thresholds)
- [ ] Verify byte order (BE vs LE) with live CAN data from Link
- [ ] Test: rotate SI-Drive knob, confirm shift LED thresholds change
- [ ] Save RS3 config to laptop and to `rs3/` in kisti repo

## Files Referenced

| File | Relevance |
|------|-----------|
| `can/can_config.py:380-385` | AiM shift LEDs not CAN-addressable |
| `can/can_config.py:244-255` | SI-Drive frame layout + OEM remapping |
| `can/can_config.py:179-242` | Generic Dash frame layouts (RPM source) |
| `can/can_config.py:86` | CAN bitrate: 1 Mbps |
| `data/build_record.py:123` | AiM Strada 7" Street Edition |
| `data/build_record.py:120` | Link G5 Neo 4 |
