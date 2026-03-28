#!/bin/bash
# Auto-commit uncommitted changes on the Jetson every 5 minutes
# Prevents work loss from ungraceful shutdowns / power cycles
REPO="$HOME/repos/kisti"
cd "$REPO" || exit 1

# Only commit if there are actual changes
if [ -n "$(git status --porcelain)" ]; then
    git add -A
    git commit -m "auto: Jetson working state $(date '+%Y-%m-%d %H:%M')"
    # Push to origin if network is available
    ping -c 1 -W 2 github.com &>/dev/null && git push origin main 2>/dev/null
fi
