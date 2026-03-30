#!/bin/bash
# KiSTI — Test iPhone hotspot connectivity + rclone Nextcloud sync
# Run on Jetson: sudo bash scripts/test_hotspot_sync.sh
# Requires sudo for nmcli network control on Jetson

set -e

echo "=== KiSTI Hotspot Sync Test ==="
echo ""

# Check sudo
if [ "$(id -u)" -ne 0 ]; then
    echo "Need sudo for network control. Re-running..."
    exec sudo bash "$0" "$@"
fi

# 1. Drop home WiFi
echo "[1/5] Disconnecting Heckler..."
nmcli con down Heckler 2>/dev/null || echo "  (Heckler was not active)"

# 2. Wait for iPhone hotspot auto-connect
echo "[2/5] Waiting for iPhone hotspot (up to 30s)..."
for i in $(seq 1 30); do
    if nmcli -t -f NAME connection show --active 2>/dev/null | grep -qi iphone; then
        echo "  Connected to iPhone hotspot after ${i}s"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "  FAILED — iPhone hotspot did not connect in 30s"
        echo "  Reconnecting Heckler..."
        nmcli con up Heckler 2>/dev/null
        exit 1
    fi
    sleep 1
done

# 3. Verify internet
echo "[3/5] Testing internet connectivity..."
if ping -c 2 -W 3 8.8.8.8 > /dev/null 2>&1; then
    echo "  Internet OK"
else
    echo "  FAILED — no internet over hotspot"
    nmcli con up Heckler 2>/dev/null
    exit 1
fi

# 4. Test rclone Nextcloud access
echo "[4/5] Testing rclone Nextcloud sync..."
if rclone lsd kisti: --max-depth 1 2>/dev/null; then
    echo "  Nextcloud reachable via rclone"
else
    echo "  FAILED — rclone cannot reach Nextcloud"
    nmcli con up Heckler 2>/dev/null
    exit 1
fi

# 5. Restore home WiFi
echo "[5/5] Reconnecting Heckler..."
nmcli con up Heckler 2>/dev/null || true

echo ""
echo "=== HOTSPOT SYNC TEST PASSED ==="
