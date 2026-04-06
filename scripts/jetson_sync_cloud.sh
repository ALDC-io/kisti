#!/bin/bash
# Sync KiSTI data to Nextcloud daily
# Exports weather, FLIR thermal, database backups, memories, and LLM config
REPO="$HOME/repos/kisti"
cd "$REPO" || exit 1

python3 scripts/sync_to_cloud.py >> /tmp/kisti_sync_cloud.log 2>&1
