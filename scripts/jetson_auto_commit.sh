#!/bin/bash
# Auto-commit uncommitted changes on the Jetson every 5 minutes.
# Prevents work loss from ungraceful shutdowns / power cycles.
REPO="$HOME/repos/kisti"
cd "$REPO" || exit 1

if [ -n "$(git status --porcelain)" ]; then
    git add -A
    git commit -m "auto: Jetson working state $(date '+%Y-%m-%d %H:%M')"
fi

# Push current branch to its upstream if reachable.
BRANCH=$(git rev-parse --abbrev-ref HEAD)
if ping -c 1 -W 2 github.com &>/dev/null; then
    git push origin "$BRANCH"
fi
