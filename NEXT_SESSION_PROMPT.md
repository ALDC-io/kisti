# KiSTI Next Session Handoff

**Repo**: `/home/aldc/repos/kisti/` | **Branch**: `kisti-headless`
**Jetson**: `192.168.22.131` (SSH user: `aldc`, pw: `aldc1234`)
**935 tests passing** — `python3 -m pytest tests/ -x -q`

---

## What Was Done (This Session)

### Coaching Screens Phases 2-5 COMPLETE (commit a3eb24c)
- **Phase 2**: Voice ticker on all 3 screens (last 3 spoken lines, alpha fade)
- **Phase 3**: `coaching/technique_analyzer.py` — 30s rolling window, brake/steering/trail-braking (Sport screen)
- **Phase 4**: `coaching/condition_rules.py` — 8 rules (ice risk, wet, oil temp, etc.), CoachingLevel-filtered (Intelligent screen)
- **Phase 5**: `_sector_insight()` in sharp_screen.py — "big gain"/"lost time"/"a bit slow" per sector (Sport# screen)
- **Layout**: G magnitude inside circle at `cy + r1*0.45 = 313`, coaching text at y=398 (Sport)

### Deployed to Jetson
- `git pull --ff-only` succeeded on Jetson (14 files, 1009 insertions)
- GDM restarted — **BUT: GNOME came back** (see issue #1 below)

---

## Issues To Fix First

### Issue 1: GNOME is back on Jetson — MUST FIX BEFORE KISTI WORKS
The `systemctl restart gdm` re-enabled GNOME, clobbering the getty+startx headless setup from kisti-19.
KiSTI won't display on Excelon until this is fixed.

**Fix path** (from kisti-19 learnings):
```bash
ssh aldc@192.168.22.131
# Kill GNOME, restore headless boot
sudo systemctl disable gdm
sudo systemctl stop gdm
# Verify startx still configured (check ~/.bash_profile for startx line)
cat ~/.bash_profile
# If startx line is gone, re-add: if [ -z "$DISPLAY" ] && [ "$(tty)" = "/dev/tty1" ]; then exec startx; fi
# Reboot to verify
echo aldc1234 | sudo -S reboot
```
After reboot, KiSTI should auto-start on HDMI-0 via startx → `~/repos/kisti/scripts/kisti-session`.

**DO NOT use `systemctl restart gdm` again** — that's what broke it. The correct deploy command is:
```bash
ssh aldc@192.168.22.131 "cd ~/repos/kisti && git pull --ff-only && ~/k"
```
The `~/k` wrapper handles restart without touching GDM.

---

## Prioritized TODOs

### 1. Fix GNOME / headless boot (see Issue 1 above)

### 2. Fix SC-2: Shrink technique analyzer window (5-min change, high value)
`coaching/technique_analyzer.py` line 37: `_WINDOW = 30` → `_WINDOW = 10`
`coaching/technique_analyzer.py` line 38: `_MIN_SAMPLES = 10` → `_MIN_SAMPLES = 5`
Current 30s window means feedback is 20s stale. 10s makes it feel real-time.
Tests in `tests/test_technique_analyzer.py` — verify they still pass after change.

### 3. SC-6: Session-over-session trends on Intelligent screen (post-Boost Barn)
**Do NOT tackle SC-6 until after Boost Barn validation session with real ECU data.**
Reason: mock data brake pressure thresholds may need recalibration once real Link ECU values are flowing.
When ready: new file `coaching/session_trend_analyzer.py` — query DuckDB `telemetry` table for brake_pressure std dev trend across last 3 sessions. Surface in 3rd column of Intelligent status strip (y=340..480).

---

## Coaching Screen Scores (SC-1 through SC-6)
These criteria were never formally added to README.md — add them when convenient.

| SC | Criterion | Score | Gap |
|----|-----------|-------|-----|
| SC-1 | Coaching visible on all 3 screens | 7/10 | Sport 13pt in G-circle corner is borderline readable at speed |
| SC-2 | Technique feedback (brake/steer/trail) | 5/10 | 30s window = forensics not coaching. Fix: 10s |
| SC-3 | Condition-aware coaching | 8/10 | Only fires on Intelligent. WET/LOW_GRIP in Sport mode goes uncoached |
| SC-4 | Mode-appropriate verbosity | 8/10 | Philosophy correct and implemented |
| SC-5 | Sector insight on Sport# | 5/10 | 500ms hardcoded threshold; 9pt text; no compound insight |
| SC-6 | Session-over-session trends | 0/10 | Not built. Data is in DuckDB, just no query+display layer |

**Overall: 33/60 = 55%.** Coaches in the moment. Has no memory. SC-6 is the differentiator.

---

## Key Files

| File | Role |
|------|------|
| `ui/sport_screen.py` | G label at `cy + r1*0.45 = 313`, coaching at y=398 |
| `ui/intelligent_screen.py` | Coaching replaces sublabel at y=card_y+90 |
| `ui/sharp_screen.py` | `_sector_insight()` static method, sector text at 9pt |
| `coaching/technique_analyzer.py` | 30s rolling window (→ fix to 10s), Sport screen |
| `coaching/condition_rules.py` | 8 condition-action rules, Intelligent screen |
| `data/duckdb_store.py` | `telemetry` table has brake_pressure/steering_angle per session |
| `timing/timing_manager.py` | Sector timing, feeds Sport# sector blocks |
| `main.py` | 1Hz timers, voice ticker deque, all screen wiring |
| `scripts/deploy-to-jetson.sh` | SSH deploy (use `~/k` wrapper on Jetson for restart) |

## Architecture Reminders
- Paint pattern: coaching cached in instance vars (1Hz), painted at 20Hz. Zero compute in paintEvent.
- No Qt in coaching modules — pure Python, fully testable.
- G circle geometry Sport: center=(575, 250), radius=140. Label at cy + r1*0.45 = 313.
- CPU: 527% / 600% — pre-existing (whisper VAD threads). Coaching adds ~0.5ms/s.
- Tests baseline: 935. Must not regress.
- **NEVER use `systemctl restart gdm`** — breaks headless display setup.
