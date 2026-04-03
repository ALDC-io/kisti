# KiSTI Next Session Handoff

**Repo**: `/home/aldc/repos/kisti/` | **Branch**: `kisti-headless`
**Jetson**: `192.168.22.131` (SSH user: `aldc`, pw: `aldc1234`)
**935 tests passing** — `python3 -m pytest tests/ -x -q`

---

## What Was Done (This Session)

### GNOME / Headless Boot Fixed (commit 6bf1e0b)
- GDM was re-enabled by `systemctl restart gdm` last session
- Fixed: `sudo systemctl disable gdm && sudo systemctl stop gdm && reboot`
- Verified: post-reboot GDM=inactive, Xorg on `:0 vt1`, getty autologin working
- KiSTI auto-launches `--fullscreen` via startx → `kisti-session` script as expected

### SC-2 Fixed: Technique analyzer window 30s → 10s (commit 6bf1e0b)
- `coaching/technique_analyzer.py`: `_WINDOW=10`, `_MIN_SAMPLES=5`
- 8/8 technique analyzer tests pass
- Deployed to Jetson via `git pull --ff-only && ~/k`

### SC-6 Readiness Check
- DuckDB at `/data/duckdb/kisti.duckdb` — 18 tables, schema is fully built
- `telemetry` table: **0 rows** — no real sessions yet (pre-Boost Barn)
- SC-6 is NOT ready. Do not implement until after Boost Barn real ECU data flows

---

## Coaching Screen Scores (SC-1 through SC-6)

| SC | Criterion | Score | Gap |
|----|-----------|-------|-----|
| SC-1 | Coaching visible on all 3 screens | 7/10 | Sport 13pt in G-circle corner is borderline readable at speed |
| SC-2 | Technique feedback (brake/steer/trail) | 7/10 | Fixed: 10s window — real-time now ✓ |
| SC-3 | Condition-aware coaching | 8/10 | Only fires on Intelligent. WET/LOW_GRIP in Sport goes uncoached |
| SC-4 | Mode-appropriate verbosity | 8/10 | Philosophy correct and implemented |
| SC-5 | Sector insight on Sport# | 5/10 | 500ms hardcoded threshold; 9pt text; no compound insight |
| SC-6 | Session-over-session trends | 0/10 | Not built. Blocked on real ECU data (post-Boost Barn) |

**Overall: 35/60 = 58%.** SC-2 now real-time coaching. SC-6 is the differentiator.

---

## Prioritized TODOs

### 1. SC-6: Session-over-session trends (POST-Boost Barn only)
**Do NOT tackle until Boost Barn validation session confirms real ECU brake_pressure values.**
- New file `coaching/session_trend_analyzer.py`
- Query DuckDB `telemetry` table for brake_pressure std dev trend across last 3 sessions
- Surface in 3rd column of Intelligent status strip (y=340..480)
- DuckDB path: `/data/duckdb/kisti.duckdb` (NOT `~/repos/kisti/data/`)

### 2. SC-5 improvements (optional, low urgency)
- Replace 500ms hardcoded threshold with adaptive per-sector baseline
- Bump sector text from 9pt → 11pt
- Add compound insight ("gained 0.3s — trail braking better")

### 3. SC-3 gap: WET/LOW_GRIP coaching on Sport screen (optional)
- Condition rules currently only surface on Intelligent screen
- Could surface a stripped-down alert on Sport too

---

## Key Files

| File | Role |
|------|------|
| `ui/sport_screen.py` | G label at `cy + r1*0.45 = 313`, coaching at y=398 |
| `ui/intelligent_screen.py` | Coaching replaces sublabel at y=card_y+90 |
| `ui/sharp_screen.py` | `_sector_insight()` static method, sector text at 9pt |
| `coaching/technique_analyzer.py` | 10s rolling window (fixed), Sport screen |
| `coaching/condition_rules.py` | 8 condition-action rules, Intelligent screen |
| `data/duckdb_store.py` | `telemetry` table — brake_pressure/steering_angle per session |
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
- **Deploy command**: `ssh aldc@192.168.22.131 "cd ~/repos/kisti && git pull --ff-only && ~/k"`
- **DuckDB path on Jetson**: `/data/duckdb/kisti.duckdb` (not in repo dir)
