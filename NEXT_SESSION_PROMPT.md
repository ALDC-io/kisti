# KiSTI Next Session Handoff

**Repo**: `/home/aldc/repos/kisti/` | **Branch**: `kisti-headless`
**Jetson**: `192.168.22.131` (SSH user: `aldc`, pw: `aldc1234`)
**935 tests passing** — `python3 -m pytest tests/ -x -q`

---

## What Was Done (This Session)

### Coaching Screens Phases 1-6 COMPLETE
All 3 SI-Drive screens (Sport, Intelligent, Sport#) now actively coach the driver.

- **Phase 2**: Voice ticker on all 3 screens — last 3 spoken lines with alpha fade
- **Phase 3**: `coaching/technique_analyzer.py` — 30s rolling window, brake/steering/trail-braking feedback on Sport screen
- **Phase 4**: `coaching/condition_rules.py` — 8 rules (ice risk, wet surface, oil temp, etc.), CoachingLevel filtered (K5 button)
- **Phase 5**: Sport# sector insight — `_sector_insight()` adds "big gain"/"lost time"/"a bit slow" to sector blocks
- **Layout fix**: G magnitude moved inside G circle (lower interior at `cy + r1*0.45`) on Sport screen — was floating orphaned below circle
- **Committed + pushed**: `6fffe11` on `kisti-headless`

## Not Yet Done
- **Deploy to Jetson**: commit pushed, Jetson NOT updated yet (`git pull` + GDM restart not run)
- **Coaching score assessment**: User asked "how do you score us for helping the driver be a better driver?" — not answered
- **SC-6 (edge memory trends)**: Session-over-session DuckDB trends still NOT surfacing on screen

---

## First Thing: Deploy to Jetson
```bash
ssh aldc@192.168.22.131 "cd ~/repos/kisti && git pull --ff-only && echo aldc1234 | sudo -S systemctl restart gdm"
```
Then visually verify G label sits inside circle on Sport screen.

---

## Prioritized TODOs

### 1. Score the coaching screens (answer user's question)
Honest assessment against SC-1 to SC-7 (see `README.md`). Key gaps:
- SC-6 NOT DONE — DuckDB session trends not visible on screen. Driver can't see "braking improved 12%".
- SC-2 (technique feedback): 30s window is slow to respond. Could go 10s.

### 2. SC-6: Edge Memory Trends (Next Phase)
`ui/intelligent_screen.py` status strip (y=340..480) has room for a 3rd column.
New file needed: `coaching/session_trend_analyzer.py` — query DuckDB `sessions` table for brake consistency trend over last 3 sessions.

### 3. Check voice ticker overlap on Sport
Ticker at y=106-136 in G circle area (x=360-790). Verify no overlap with circle labels when voice is active.

---

## Key Files

| File | Role |
|------|------|
| `ui/sport_screen.py` | G label now at `cy + r1*0.45 = 313`, coaching at y=398 |
| `ui/intelligent_screen.py` | Coaching replaces "ROAD TEMPERATURE" sublabel |
| `ui/sharp_screen.py` | `_sector_insight()` static method, sector text |
| `coaching/technique_analyzer.py` | 30s rolling brake/steering/trail-braking |
| `coaching/condition_rules.py` | 8 condition-action rules, priority + level filter |
| `main.py` | 1Hz timers, voice ticker deque wired to all screens |

## Architecture Reminders
- Paint pattern: coaching cached in instance vars (1Hz), painted at 20Hz. Zero compute in paintEvent.
- No Qt in coaching modules — pure Python, fully testable.
- G circle geometry Sport: center=(575, 250), radius=140. Label now at cy + r1*0.45 = 313.
- CPU: 527% / 600% — pre-existing (whisper VAD threads). Coaching adds ~0.5ms/s.
- Tests baseline: 935. Must not regress.
