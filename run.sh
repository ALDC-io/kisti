#!/bin/bash
# KiSTI launcher
# Handles LD_LIBRARY_PATH for user-installed xcb-cursor

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export DISPLAY="${DISPLAY:-:0}"
export LD_LIBRARY_PATH="$HOME/.local/lib:${LD_LIBRARY_PATH:-}"

exec python3 "$SCRIPT_DIR/main.py" "$@"
