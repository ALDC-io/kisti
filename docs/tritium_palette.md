# Tritium-Heritage Colour Reference

**Aesthetic brief:** Sinn 856 UTC tritium tubes, not green LEDs.
Green-tinted white that reads as luminescent, not decorative.
Reference: Porsche 917 dashboard / radium-dial instruments.

---

## Primary Palette

| Role | Hex | RGB | Notes |
|------|-----|-----|-------|
| Instrument primary (WHITE) | `#D4E8D0` | 212, 232, 208 | Tick marks, numerals, needle |
| Instrument secondary | `#B8D0B8` | 184, 208, 184 | Minor ticks, sub-labels |
| Dimmed / dark-cockpit text | `#6A8A6A` | 106, 138, 106 | Normal-state vitals |
| Subtle lines / grid / rings | `#2A3A2A` | 42, 58, 42 | Ring edges, separators |
| Face background | `#0A0A0A` | 10, 10, 10 | Near-black gauge face |

## Alert Palette (NEVER SUBSTITUTE)

| Role | Hex | RGB | Notes |
|------|-----|-----|-------|
| Redline + alert-ack | `#FFB000` | 255, 176, 0 | Amber — holds against green-white |
| Caution / warning | `#FFAA00` | 255, 170, 0 | Standard amber |
| Critical warnings | `#FF1A1A` | 255, 26, 26 | Red — unchanged |

## Lighting Targets (trim/shop brief)

| Location | Hex | RGB | Notes |
|----------|-----|-----|-------|
| Keypad backlight | `#B0D8B0` | 176, 216, 176 | More saturated — reads tinted at arm's length |
| Footwell ambient | `#A8D8A8` | 168, 216, 168 | Most saturated — furthest from eye |

---

## AiM ARGB Integer Values

AiM Race Studio 3 stores colours as signed 32-bit ARGB integers.
Formula: `value = (Alpha << 24) | (Red << 16) | (Green << 8) | Blue`

| Role | Hex | Unsigned ARGB int | Signed ARGB int |
|------|-----|-------------------|-----------------|
| Instrument primary | `#FFD4E8D0` | 4291363024 | -3604272 |
| Instrument secondary | `#FFB8D0B8` | 4289299640 | -5667656 |
| Dimmed text | `#FF6A8A6A` | 4284643434 | -10323862 |
| Subtle lines | `#FF2A3A2A` | 4280162858 | -14804438 |
| Face background | `#FF0A0A0A` | 4278583818 | -16383478 |
| Amber alert | `#FFFFB000` | 4294930432 | -36864 |

---

## Substitution Table (old → new)

| Old (RS3 default) | New (tritium) | Role |
|-------------------|---------------|------|
| `#FFFFFF` / 4294967295 | `#D4E8D0` | Primary white |
| `#F0F0F0` / 4294309872 | `#D4E8D0` | Near-white |
| `#E0E0E0` / 4293256160 | `#D4E8D0` | Near-white |
| `#D0D0D0` / 4292203472 | `#B8D0B8` | Light grey |
| `#C0C0C0` / 4291150848 | `#B8D0B8` | Chrome light |
| `#B0B0B0` / 4290098160 | `#B8D0B8` | Chrome mid |
| `#A0A0A0` / 4289045472 | `#B8D0B8` | Chrome |
| `#909090` / 4287992720 | `#6A8A6A` | Mid grey |
| `#808080` / 4286611584 | `#6A8A6A` | Grey |
| `#333333` / 4281545523 | `#2A3A2A` | Dark grey |
| `#202020` / 4280295456 | `#2A3A2A` | Near black |

---

## Design Philosophy

**Dark cockpit:** normal = invisible, deviations illuminate.

- **Green-white** is the resting state of all instruments.
- **Amber** fires at redline and alert acknowledgement.
- **Red** fires for warnings only.
- Nothing glows unnecessarily.

The physical sensation target: "resting glow of a Sinn UTC tritium tube in
a dark room" — not a green gauge cluster. The warmth is in the white, not
in a separate green channel.
