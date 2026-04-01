# RS3 — Race Studio 3 Configuration

AiM MXG Strada 7" Street configuration files and documentation.

## Contents

- `shift_led_investigation.md` — SI-Drive mode-aware shift light analysis and RS3 setup guide

## Context

The AiM MXG Strada shift lights are controlled by internal firmware thresholds configured in Race Studio 3 — they are NOT addressable via CAN bus. However, the Strada sits on the same 1 Mbps CAN bus as the Link G5 Neo 4 and can receive any frame, including SI-Drive mode (0x6B0).

This enables mode-aware shift points via RS3 math channels:
- Intelligent (mode 0): shift lights disabled
- Sport (mode 1): shift at 5,500 RPM
- Sport Sharp (mode 2): shift at 6,800 RPM

## RS3 Config Files

Config files exported from Race Studio 3 should be saved here after each session. Name format: `YYYY-MM-DD_description.rs3cfg` (or whatever extension RS3 uses).
