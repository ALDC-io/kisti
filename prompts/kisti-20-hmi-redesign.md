# KiSTI-20: Visual HMI Redesign — Multi-Display Synchronized Interface

Read `NEXT_SESSION_PROMPT.md` first — it has the full context, key files, Jetson state, and test baseline (864 tests).

Use `/tui` to launch the solo agent TUI panel and post all progress events there throughout the session. Keep the TUI board updated as you complete each phase.

## What To Build

Redesign KiSTI's visual screens on the Kenwood Excelon (800x480 HDMI, QPainter/PySide6) to work as a synchronized companion to the AiM MXG Strada 7" dash, with the factory SI-Drive controller as the master mode selector.

This is a multi-display, multi-mode driver interface where SI-Drive automatically controls:
- LinkECU behavior/state
- AiM MXG Strada page set and alarm philosophy
- Kenwood Excelon (KiSTI) screen content and UI emphasis
- Voice pipeline mode (already wired in `modes/mode_manager.py`)

Both displays must always reflect the same vehicle intent. The driver gets the right information at the right time with minimal distraction.

## Phase 1: Plan (use EnterPlanMode)

Before writing any code, produce a systems design plan covering:

### Architecture
- Signal flow between Link ECU → CAN bus → Jetson → Excelon display
- SI-Drive analog voltage → LinkECU → CAN broadcast → KiSTI mode enum
- How MXG and Excelon stay synchronized (same CAN source, no middleware)
- Failure/offline behavior (graceful degradation)

### Mode Model — define INTELLIGENT, SPORT, SPORT# as full system modes:

**INTELLIGENT** — calm / safety / diagnostic / street / bad weather
- Rich context on Excelon: weather, oil/coolant trends, diagnostics, AI co-driver conversation, vehicle health
- Clean, low-density layout. Large fonts. Muted colors
- Voice: full conversational mode (frontier, jokes, memory)
- Alarms: all tiers shown, detailed text

**SPORT** — fast road / mountain road / spirited driving
- Performance-focused Excelon: boost/oil/brake sparklines, corner temps, DCCD state, gear/speed
- Medium density. Performance color palette (cyan/green accents)
- Voice: concise mode (2 sentences max)
- Alarms: caution + critical only, compact

**SPORT#** — track / attack / maximum repeatability
- Minimal distraction Excelon: lap timing, delta, brake trace, tire temps, sector splits
- Ultra-sparse. Only what matters at 10/10ths. Dark background, high contrast numbers
- Voice: critical safety only (1 sentence)
- Alarms: critical only, full-screen flash for engine protection

### Required Plan Deliverables (all three are mandatory):

1. **CAN Message Map Draft** — table of every CAN frame ID (existing 0x6A0-0x6A7 + any new), source device, destination(s), byte layout, update rate, which mode uses it. Include a new frame for SI-Drive mode broadcast if needed.

2. **Page-by-Page Widget List** — for each Excelon screen, list every widget with approximate position, data source, update rate, visual style (gauge/sparkline/number/bar/text), and font size priority. Screens needed:
   - Intelligent home
   - Sport home
   - Sport# home
   - Diagnostics/system health
   - Track/performance (Sport# sub-page)
   - Settings/config

3. **Mode Transition Sequence Diagram** — step-by-step flow when SI-Drive rotates: CAN signal read → debounce (ms target) → mode enum update → Excelon page switch → alarm profile change → voice mode change → confirmation feedback. Include failure handling.

### Additional Plan Sections:
- Alarm/warning philosophy: tiered (Info/Caution/Critical), which display shows what, mode-aware suppression
- Brake pressure integration: one front sensor first, coaching value, where it appears per mode
- Shift light awareness: KiSTI doesn't control MXG shift lights but should know shift points for context
- State machine / truth table: mode × context → display behavior, alarm overrides

## Phase 2: Implementation (after plan approval)

Build the Excelon screens in QPainter. All rendering is custom paint — no web views, no external dependencies.

Key constraints:
- 800x480 resolution (WVGA), landscape, dark automotive theme
- Must be readable at a glance while driving — large primary numbers, high contrast
- Existing `ui/theme.py` has the color palette — extend it, don't replace
- SI-Drive mode comes via CAN from `can/kisti_can.py` — wire to `modes/mode_manager.py`
- Softkey bar becomes sub-page navigation within each SI-Drive mode
- Voice pipeline stays untouched — it already responds to mode changes
- Tests must stay at 864+ — add tests for new mode switching logic

## What NOT To Do
- Do NOT redesign MXG pages — those are configured in AiM RaceStudio3
- Do NOT break the voice pipeline
- Do NOT remove existing tests
- Do NOT add Ollama/local LLM — frontier is the AI path
- Do NOT over-design — build what's needed for each mode, not race-car cosplay

## Design Principles
- SI-Drive is master — everything follows it
- MXG = critical (alarms, RPM, shift lights). Excelon = context (trends, AI, maps, history)
- Minimal cognitive load — information hierarchy matters more than signal count
- SPORT and SPORT# must feel genuinely different — not just color swaps
- INTELLIGENT must be genuinely useful — the calm, diagnostic, "tell me everything is OK" mode
- Fail safe — if CAN drops, default to Intelligent, show last-known values with staleness indicator
