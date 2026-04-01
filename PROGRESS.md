# KiSTI - Progress

## Session: 2026-04-01 (kisti-20 — HMI Redesign Phase 1 + 3 Screens)

### Status: IN PROGRESS — Display auth blocker on Jetson

### Completed
- **Systems design plan** — Full plan via EnterPlanMode + 3 parallel Explore agents. CAN map (no new frames needed), page specs, mode transition sequence.
- **Architecture simplified** — JK: "12 pages is too much, 1 per mode". No softkey bar. SI-Drive knob is only mode selector. Content area 800x440.
- **Phase 1 infrastructure** — theme mode accents, flat QStackedWidget, status bar SI-Drive badge, ModeManager staleness fallback (5s), main.py 20Hz data feed.
- **3 QPainter screens built** — IntelligentScreenWidget (blue), SportScreenWidget (amber), SportSharpScreenWidget (red). All self-contained paintEvent.
- **879 tests passing** — 864 baseline + 15 new.
- **Committed and pushed** — kisti-headless branch, commit a56fa9c/91ff768.

### Files Changed
- `ui/theme.py` — MODE_I/S/SS_ACCENT, FONT_XLARGE/MEGA
- `ui/status_bar.py` — SI-Drive badge, warmup dot, CAN dot
- `ui/main_window.py` — Flat 3-page QStackedWidget, no softkey bar, update_from_bridge()
- `modes/mode_manager.py` — SI-Drive staleness fallback, K6 reserved
- `main.py` — mode_manager kwarg, 20Hz screen feed
- `ui/intelligent_screen.py` — NEW full QPainter Intelligent screen
- `ui/sport_screen.py` — NEW full QPainter Sport screen
- `ui/sharp_screen.py` — NEW full QPainter Sport Sharp screen
- `tests/test_modes.py` — 29 tests (14 orig + 15 new)

### Key Decisions
- 3 screens only — one per SI-Drive mode, no sub-pages, no softkey bar
- QPainter-only rendering — no composite QWidget layouts inside new screens
- Zeus Memory POST accepts but GET 404 — persistence bug, use NEXT_SESSION_PROMPT.md as backup

### Blocker: Jetson Display Auth
GDM moved to Wayland. Display :1025 not :0. SSH can't get X auth. Fix: update scripts/kisti-session to auto-detect display. See NEXT_SESSION_PROMPT.md Section 2.

### Don't Repeat
- Haiku hallucinates on automotive domain specifics — always add system prompt context
- Whisper adds punctuation — ALWAYS strip before string matching
- dcli no Linux ARM64 binary
- Zeus Memory POST returns ZMID but GET 404 — don't rely on Zeus for plan storage
- Always use ZEUS_ALDC_API_KEY (management tenant) for shared Zeus memories
- SSH can't authorize to Jetson X display — must run kisti-session from GDM session or fix auth in script

### Next Session (kisti-21)
1. Fix Jetson display auth (update scripts/kisti-session)
2. Visually verify 3 screens on 800x480 Excelon
3. Alert engine mode-awareness
4. Integration tests

---

## Session: 2026-04-01 (kisti-19 — Frontier + Wake Word)
- Frontier cloud AI working, wake word punctuation fix, 864 tests passing
- Don't repeat: Whisper adds punctuation; dcli no ARM64

## Session: 2026-03-31 (kisti-18 — Streaming TTS)
- Streaming TTS 4s→1s, Whisper systemd, 864 tests
- Don't repeat: Don't truncate Intelligent mode sentences
