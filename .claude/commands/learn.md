---
name: learn
description: Capture session learnings from KiSTI work and store in Zeus Memory. Works in both CLI and Claude Code web.
---
# KiSTI Learn - Capture Session Learnings

Captures learnings from the current session and stores them in Zeus Memory. Works in both Claude Code CLI and Claude Code web (claude.ai/code).

## Triggers
- "/learn"
- "capture learnings"

## Procedure

### Step 1: Read Project Context
Read these files to understand current state:
- `PROGRESS.md` — current phase, baseline test count, Don't Repeat list
- `NEXT_SESSION_PROMPT.md` — what's in progress, what's next
- `README.md` — project overview (skim only)

### Step 2: Scan Session
Review the conversation for:
- **Failed approaches** — things that didn't work, bugs hit, wrong assumptions
- **Successes** — completed features, milestones, test count increases
- **Decisions** — architectural choices, trade-offs, pattern selections
- **Don't Repeat items** — gotchas, footguns, debugging dead-ends

### Step 3: Store Learnings in Zeus Memory

Use the `mcp__claude_ai_Zeus__remember` MCP tool for each learning. This tool works in both CLI and web.

**CRITICAL RULES:**
1. **Source field** must be one of: `cce_success_log`, `cce_failed_approach`, `cce_decision_log` — NOT `learn` or `mcp`
2. **Metadata** must include `user` and `type` fields:
   ```json
   {"type": "cce_success_log", "user": "jk", "domain": "kisti"}
   ```
3. **User is always `jk`** for KiSTI work (this is JK's personal project)

Example calls:
```
mcp__claude_ai_Zeus__remember(
    content="SUCCESS: Friction ellipse (not circle) validated by motorsport research...",
    source="cce_success_log",
    metadata={"type": "cce_success_log", "user": "jk", "domain": "kisti"}
)

mcp__claude_ai_Zeus__remember(
    content="FAILED: Rolling window outlier too extreme, flipped classification...",
    source="cce_failed_approach",
    metadata={"type": "cce_failed_approach", "user": "jk", "domain": "kisti"}
)

mcp__claude_ai_Zeus__remember(
    content="DECISION: Bicycle model primary for understeer, GPS heading secondary...",
    source="cce_decision_log",
    metadata={"type": "cce_decision_log", "user": "jk", "domain": "kisti"}
)
```

### Step 4: Update PROGRESS.md

Add a new session block at the top of PROGRESS.md with:
- **Status**: COMPLETE or IN PROGRESS
- **Completed**: bullet list of what was done
- **Key Decisions**: architectural choices with rationale
- **Don't Repeat**: gotchas and footguns discovered
- **Learnings Captured**: checklist of Zeus Memory entries with types
- **Files Changed**: list of files created/modified
- **Next Session**: prioritized TODO for next pickup

### Step 5: Show Summary

Display a table of learnings captured:
| Type | Topic | ZMID |
|------|-------|------|
| cce_success_log | ... | 8-char prefix |
| cce_failed_approach | ... | 8-char prefix |
| cce_decision_log | ... | 8-char prefix |

## Architecture Context

KiSTI is an **offline Zeus Memory edge node** — all telemetry, sessions, and analysis run locally on Jetson with DuckDB, syncing to ALDC Zeus Memory when WiFi is available. Learnings from KiSTI sessions feed into the broader Enterprise Intelligence System.

- **Repo**: `/home/aldc/repos/kisti/` (or connected via Codespace in web)
- **Branch**: `kisti-headless`
- **Jetson**: `ssh aldc@192.168.22.131`
- **Test baseline**: check `PROGRESS.md` for current count (aim: only goes up)
- **Key files**: `PROGRESS.md`, `NEXT_SESSION_PROMPT.md`, `docs/SCREEN_REDESIGN_PLAN.md`

## What NOT to Log
- Code patterns derivable from reading files
- Git history (use `git log`)
- Ephemeral task state (use PROGRESS.md instead)
- Anything already in CLAUDE.md or Don't Repeat sections

---

**Version**: 1.0.0
**Last Updated**: 2026-04-04
