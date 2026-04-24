# AiM Race Studio 3 — Tritium Theme Manual Guide

**Device:** AiM MXG 1.2  
**Car:** 2014 Subaru WRX STI  
**Project path:** `C:\AIM_SPORT\RaceStudio3`

Use this guide if the Python script (`rs3/fix_tritium.py`) cannot be run
(e.g. proprietary binary format, or manual override needed for specific elements).

---

## Before You Start

1. **Close Race Studio 3 completely** before any file edits.
2. Keep `docs/tritium_palette.md` open for colour reference.
3. Make a backup of `C:\AIM_SPORT\RaceStudio3` before editing.
4. After any edit: **File → Save → Transmit to device immediately**.
   Do not do other edits between Save and Transmit — RS3 caches state.

---

## Workflow: Editing via RS3 GUI

### Opening the Dashboard Editor

1. Launch Race Studio 3
2. **File → Open Project** → navigate to `C:\AIM_SPORT\RaceStudio3`
3. Select your `.aimdev2` project file
4. Click **Dashboard** tab (left panel)
5. Double-click a page to open it in the editor

### Selecting a Gauge Element

1. Click once on a gauge (tachometer, speedometer, etc.)
2. Right-click → **Properties** (or press F4)
3. The properties panel opens on the right

### Changing a Colour

1. In Properties, find the colour field (e.g. "Foreground Color", "Label Color")
2. Click the colour swatch to open the colour picker
3. Switch to **Custom** tab
4. Enter the hex value from the palette table below
5. Click **OK**
6. Repeat for each colour field

---

## Colour Changes by Element Type

### Gauge Face Numerals (labels: 0, 1, 2 … 8 on tachometer)

| Field | Old | New hex | New RGB |
|-------|-----|---------|---------|
| Label Color / Text Color | `#FFFFFF` | `#D4E8D0` | 212, 232, 208 |
| Secondary Label Color | `#D0D0D0` | `#B8D0B8` | 184, 208, 184 |

### Tick Marks (major and minor)

| Field | Old | New hex | New RGB |
|-------|-----|---------|---------|
| Major Tick Color | `#FFFFFF` | `#D4E8D0` | 212, 232, 208 |
| Minor Tick Color | `#D0D0D0` | `#B8D0B8` | 184, 208, 184 |

### Needle

| Field | Old | New hex | New RGB |
|-------|-----|---------|---------|
| Needle Color | any white/grey | `#FFB000` | 255, 176, 0 (amber) |

**Note on needle colour persistence:** RS3 may revert needle colour on
transmit from its internal cache. If it reverts:
- Edit via the GUI colour picker (not via file edit)
- Save the project, then immediately Transmit — do not reopen the file
- If it still reverts, edit the needle color in the XML inside the `.aimdev2`
  ZIP file AND in the `dev_*.aimdev2` sidecar file (same colour change in both)

### Background (gauge face)

| Field | Old | New hex | New RGB |
|-------|-----|---------|---------|
| Background Color | `#000000` | `#0A0A0A` | 10, 10, 10 |

### Ring / Bezel (chrome surround)

These are the chrome rings around each gauge. To fix **ring gaps (holes)**:

1. Click the bezel/ring element
2. In Properties find **Sweep Angle** (or Span Angle / Arc Sweep)
3. **Set Sweep Angle = 360**
4. Set **Start Angle = 0**
5. Set the ring color to `#2A3A2A` (subtle tritium-tinted dark ring edge)

This ensures the ring is a complete circle with no gap.

### Separator Lines / Grid

| Field | Old | New hex | New RGB |
|-------|-----|---------|---------|
| Line Color / Grid Color | any grey | `#2A3A2A` | 42, 58, 42 |

### Redline Zone / Warning Arc

**DO NOT CHANGE.** Leave all redline arcs, warning zones, and alert
indicators at their original colours. The amber and red safety colours
are intentional and must not be modified.

| Zone | Colour to keep |
|------|---------------|
| Redline arc | Red `#FF1A1A` or `#FF0000` |
| Caution arc | Amber `#FFAA00` |
| Alert acknowledgement | `#FFB000` |

---

## Fixing Ring Gaps — Step by Step

The ring gaps (holes) appear when a bezel/ring element is configured as a
partial arc instead of a full circle.

1. In the dashboard editor, click the outer chrome ring of any gauge
2. Open Properties (F4)
3. Find the **Sweep Angle** field — it may show 240°, 270°, 300°, etc.
4. Change it to **360**
5. Find **Start Angle** — change to **0**
6. Repeat for each gauge: tachometer, speedometer, and auxiliary gauge
7. Save and transmit

If the ring element is a background (filled circle), also check:
- **Inner Radius** is set correctly (should be less than Outer Radius)
- **Background Fill** is set to a colour (not transparent) — use `#0A0A0A`

---

## Three Gauge Variants

Apply the same changes to all three overlay variants:

| Variant | Notes |
|---------|-------|
| `mxg_12` | Main display |
| `mxg_12 strada` | Street/road layout variant |
| `fsw` | Fuji Speedway / track-specific layout |

---

## Transmit Procedure

1. **Save** the project (Ctrl+S)
2. Connect the AiM MXG via USB or WiFi
3. **Device → Transmit**
4. Wait for complete transfer — do not interrupt
5. Power cycle the device
6. Verify on device: rings complete, needle amber, numerals tritium green-white

---

## Troubleshooting

**Colour reverts after transmit:**  
RS3 has a compiled `.cff` display cache. To bust it:
- Close RS3 fully
- In `C:\AIM_SPORT\RaceStudio3`, find and delete (or rename) any `disp.cff` file
- Reopen RS3 — it will recompile from XML source
- Transmit immediately

**Needle colour keeps reverting:**  
The `dev_*.aimdev2` sidecar contains a deeper copy. Edit the needle
colour directly in RS3's GUI (not via file edit) and transmit immediately
without closing RS3.

**Ring gap returns after transmit:**  
The bezel sweep angle is stored in two places: the page XML and the
compiled display cache. Use `rs3/fix_tritium.py` to patch both simultaneously,
or patch both the `.aimdev2` main file and any `.cff` cache files.
