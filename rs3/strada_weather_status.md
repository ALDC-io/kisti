# AiM Strada — Weather Status Display Configuration

CAN frame 0x6C2 byte 0 carries KiSTI weather/road condition status. Configure a **Status** element in Race Studio 3 to display it on the Strada 7".

## CAN Channel Setup

1. Open Race Studio 3 > **Channels** > **CAN Channels**
2. Add new channel:
   - **Name**: `KISTI_Alert`
   - **CAN ID**: `0x6C2` (1730 decimal)
   - **Byte offset**: 0
   - **Data type**: Unsigned 8-bit
   - **Bit length**: 8
   - **Min**: 0, **Max**: 5
   - **Units**: (leave blank)

## Status Element Configuration

1. Go to **Display** > **Pages** > add or edit a page
2. Add a **Status** element
3. Bind to channel `KISTI_Alert`
4. Configure value-to-label mapping:

| Value | Label    | Color          | Notes                    |
|-------|----------|----------------|--------------------------|
| 0     | OK       | Green (#00CC66)| Nominal — dark cockpit   |
| 1     | WET      | Blue (#0088FF) | Wet road surface (RWIS)  |
| 2     | ICY      | Cyan (#00DDFF) | Icy/snowy/frosty road    |
| 3     | RAIN     | Orange (#FF8800)| Rain likely (barometric) |
| 4     | STORM    | Red (#FF2222)  | Severe weather or event  |
| 5     | CLOSURE  | Red flash      | Road closure             |

## Alarm Thresholds

Configure alarms to trigger visual overlays on the Strada:

| Threshold | Condition        | Alarm Type      |
|-----------|-----------------|-----------------|
| >= 2      | ICY or worse    | Warning (yellow)|
| >= 4      | STORM or worse  | Alarm (red)     |
| == 5      | CLOSURE         | Critical (flash)|

## Data Sources

The 0x6C2 status byte fuses three independent data sources, prioritized:

1. **DriveBC RWIS** — hyperlocal road surface condition from nearest weather station (WET, ICY, SNOWY, etc.)
2. **Environment Canada** — regional severe weather alerts (warning/watch level)
3. **WeatherEngine** — onboard barometric pressure trend analysis (RAIN_LIKELY, STORM from rate-of-change)

Higher-priority sources override lower ones. Road closure always wins.

## Testing

Verify with `cansend` on the Jetson (requires `can-utils`):

```bash
# OK (0)
cansend can0 6C2#00

# WET (1)
cansend can0 6C2#01

# ICY (2)
cansend can0 6C2#02

# RAIN (3)
cansend can0 6C2#03

# STORM (4)
cansend can0 6C2#04

# CLOSURE (5)
cansend can0 6C2#05
```

## Frame Specification

- **CAN ID**: 0x6C2 (standard, not extended)
- **DLC**: 1 byte (bytes 1-7 reserved, sent as zeros)
- **Transmit rate**: 10 Hz (every 100 ms)
- **Source**: KiSTI CanOutputThread on Jetson
