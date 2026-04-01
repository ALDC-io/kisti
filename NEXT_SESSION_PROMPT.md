# KiSTI — Next Session Prompt (kisti-20: Visual HMI Redesign)

**Working dir**: `/home/aldc/repos/kisti/`
**Jetson**: `192.168.22.131` (user `aldc`). SSH: `ssh aldc@192.168.22.131`
**Test baseline**: 879 tests passing (864 original + 15 new)
**Branch**: `kisti-headless`
**Latest commit**: `a56fa9c` pushed to origin

## Section 1: What Was Done (kisti-20 session)

### Phase 1 Infrastructure — COMPLETE
All files committed and pushed. 879 tests passing.

- **`ui/theme.py`**: Added `MODE_I_ACCENT=#00AAFF`, `MODE_S_ACCENT=#FF8800`, `MODE_SS_ACCENT=#FF0000`, `FONT_XLARGE=36`, `FONT_MEGA=48`
- **`ui/softkey_bar.py`**: Rewritten with 4 dynamic buttons + mode-colored highlights. BUT softkey bar is now REMOVED from main_window.py — SI-Drive is the only mode selector, no on-screen navigation
- **`modes/mode_manager.py`**: K6 reserved (no sub-pages), SI-Drive staleness fallback (5s → Intelligent), `subpage_changed` signal added but unused
- **`ui/status_bar.py`**: SI-Drive badge (colored pill), warm-up state indicator, CAN status dot. Methods: `set_si_drive_mode(int)`, `set_warmup_state(int)`, `set_can_status(bool)`
- **`ui/main_window.py`**: Flat 3-page QStackedWidget (no nesting, no softkey bar). Content area 800x440. Accepts `mode_manager` param. `_on_si_drive_changed(mode_int)` switches screens. `update_from_bridge(snap)` feeds DiffState to active screen
- **`main.py`**: Passes `mode_manager=mode_mgr` to MainWindow. Wires `bridge.state_changed` → `window.update_from_bridge(snap)` at 20Hz

### 3 New Screens — COMPLETE (code written, NOT yet visually verified)

- **`ui/intelligent_screen.py`** — `IntelligentScreenWidget`: QPainter, blue accent. Gear/speed, boost bar, oil/coolant sparklines (deque 200), weather card, lambda bar, injector duty, GPS status, DCCD overview. 1Hz repaint timer for no-data state.
- **`ui/sport_screen.py`** — `SportScreenWidget`: QPainter, amber accent. Gear/speed/RPM, boost arc gauge, oil/coolant sparklines, DCCD bar, brake pressure, G-force circle with 100-dot trail, wheel speed delta bars (FL/FR/RL/RR), slip delta.
- **`ui/sharp_screen.py`** — `SportSharpScreenWidget`: QPainter, red accent. Delta bar (full-width), lap time 48px, predicted/best, sector splits, gear 120px, brake/throttle trace (400-sample scrolling strip), dim safety vitals that light up on warnings. Has `update_timing(timing_data: dict)` for TimingManager integration.

### Tests — 879 passing
- `tests/test_modes.py`: 29 tests covering SI-Drive transitions, staleness fallback, status bar, MainWindow stack switching

## Section 2: BLOCKER — Jetson Display Auth

KiSTI won't show on the Excelon because SSH can't get X authorization for the GDM desktop session.

**The problem**: The Jetson runs GDM with auto-login. The X display is `:1025` (Xwayland), not `:0`. The Xauthority cookie is at `/run/user/1000/gdm/Xauthority` but SSH sessions can't use it (Authorization required error). The old `kisti-session` script assumed `DISPLAY=:0` which no longer exists.

**What needs to happen** (one of these):
1. **Fix kisti-session script** to auto-detect the display: `DISPLAY=$(ls /tmp/.X*-lock | tail -1 | sed 's|/tmp/.X||;s|-lock||')` and copy the Xauthority cookie
2. **OR** from a terminal INSIDE the GDM session (not SSH), run: `DISPLAY=:1025 XAUTHORITY=/run/user/1000/gdm/Xauthority python3 main.py --fullscreen`
3. **OR** configure GDM to use kisti-session as the X session (like it was before), which gives KiSTI its own X server at `:0`
4. **OR** use `loginctl` to get the session's environment and inject it

**Fastest path**: Update `scripts/kisti-session` to auto-detect display number and copy the auth cookie. Then it can be run from SSH.

## Section 3: Remaining TODO

### Immediate (to see the screens):
- [ ] Fix Jetson display auth (see Section 2)
- [ ] Verify all 3 screens render correctly on 800x480 Excelon
- [ ] Adjust layout/sizing based on visual review

### Phase 5: Alert Engine Mode-Awareness
- [ ] Add `set_si_drive_mode()` to `alerts/alert_engine.py`
- [ ] Mode-aware suppression in `_fire()`: INFO suppressed in S/S#, ADVISORY suppressed in S#, CRITICAL always fires
- [ ] `ui/widgets/critical_flash_overlay.py` — red flash overlay for S# critical alerts
- [ ] Tests for mode suppression

### Phase 6: Integration & Polish
- [ ] Final data routing verification
- [ ] Integration tests
- [ ] Update NEXT_SESSION_PROMPT.md and PROGRESS.md

## Section 4: Key Files

| File | What It Does |
|------|-------------|
| `ui/main_window.py` | Flat 3-page QStackedWidget, SI-Drive switching, no softkey bar |
| `ui/intelligent_screen.py` | **NEW** — Intelligent mode full QPainter screen |
| `ui/sport_screen.py` | **NEW** — Sport mode full QPainter screen |
| `ui/sharp_screen.py` | **NEW** — Sport Sharp mode full QPainter screen |
| `ui/status_bar.py` | SI-Drive badge, warm-up, CAN dot |
| `ui/theme.py` | Mode accent colors, font sizes |
| `modes/mode_manager.py` | SI-Drive routing, staleness fallback |
| `alerts/alert_engine.py` | Threshold alerts (needs mode-aware suppression) |
| `main.py` | Signal wiring, screen data feed at 20Hz |
| `scripts/kisti-session` | Jetson X session launcher (NEEDS display auto-detect fix) |
| `tests/test_modes.py` | 29 tests for Phase 1 |

## Section 5: Architecture

3 screens in a flat QStackedWidget. SI-Drive physical knob (CAN 0x6B0) is the ONLY mode selector. No softkey bar, no sub-pages. Content area is 800x440 (40px status bar above).

```
QStackedWidget (3 pages)
  [0] IntelligentScreenWidget  — calm/diagnostic (blue #00AAFF)
  [1] SportScreenWidget        — performance (amber #FF8800)
  [2] SportSharpScreenWidget   — track attack (red #FF0000)
```

Signal flow: CAN 0x6B0 → bridge.update_si_drive() → ModeManager.si_drive_changed → MainWindow._on_si_drive_changed() → stack.setCurrentIndex()

Data flow: bridge.state_changed → window.update_from_bridge(snap) → active_widget.update_state(snap)

## Section 6: Zeus Memory

Plan stored as ZMID `32b4a6f5-5936-461b-8b89-543edf509cd9` (management tenant) — but Zeus GET returns 404 despite POST succeeding. There's a persistence bug in Zeus Memory. The plan content is fully captured in this file instead.

Architecture decision also stored by Cowork: ZMID `54e26e48` — "3 screens, no sub-pages, no softkey bar."

## Section 7: Key Decisions

- **3 screens only** — JK explicitly said "12 pages is too much, 1 per mode." No sub-pages, no settings in driving screens
- **No softkey bar** — removed entirely. SI-Drive physical knob handles mode selection
- **Content area 800x440** — reclaimed 60px from removed softkey bar
- **QPainter only** — all screens are self-contained paintEvent rendering, no composite QWidget layouts
- **Voice pipeline untouched** — already mode-aware, no changes needed
