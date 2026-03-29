#!/bin/bash
# KiSTI Jetson System Configuration
#
# Installs all system-level configs needed for KiSTI to run as
# the sole X session on a Jetson Orin Nano. Idempotent — safe to re-run.
#
# Run as: sudo bash scripts/jetson/install-system.sh
# Requires: KiSTI repo at ~/repos/kisti, kisti-session already installed

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== KiSTI System Config Install ==="

# 1. Yoctopuce USB permissions (ambient weather sensor)
echo "Installing Yoctopuce udev rule..."
cp "$SCRIPT_DIR/99-yoctopuce.rules" /etc/udev/rules.d/
udevadm control --reload-rules
udevadm trigger
echo "  Done — Yoctopuce USB devices now world-readable/writable"

# 2. GDM autologin
echo "Configuring GDM autologin..."
cp "$SCRIPT_DIR/gdm-custom.conf" /etc/gdm3/custom.conf
echo "  Done — aldc will auto-login on boot"

# 3. AccountsService persistence (GDM wipes this on restart)
echo "Installing AccountsService restore service..."
cp "$SCRIPT_DIR/kisti-session-user" /etc/kisti-session-user
cp "$SCRIPT_DIR/kisti-session-user" /var/lib/AccountsService/users/aldc
cp "$SCRIPT_DIR/kisti-accountsservice.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable kisti-accountsservice.service
echo "  Done — kisti-session persists across GDM restarts"

# 4. Disable kisti.service (conflicts with GDM kisti-session)
if systemctl is-enabled kisti.service &>/dev/null; then
    echo "Disabling kisti.service (GDM session is the intended startup path)..."
    systemctl stop kisti.service 2>/dev/null || true
    systemctl disable kisti.service
    echo "  Done — kisti.service disabled"
else
    echo "kisti.service already disabled or not installed"
fi

# 5. KiSTI X session (if not already installed)
KISTI_REPO="$(dirname "$(dirname "$SCRIPT_DIR")")"
if [ ! -f /usr/local/bin/kisti-session ]; then
    echo "Installing KiSTI X session..."
    cp "$KISTI_REPO/scripts/kisti-session" /usr/local/bin/kisti-session
    chmod +x /usr/local/bin/kisti-session
    cp "$KISTI_REPO/scripts/kisti-session.desktop" /usr/share/xsessions/
    echo "  Done"
else
    echo "KiSTI X session already installed"
fi

# 6. rclone (for Nextcloud sync)
if ! command -v rclone &>/dev/null; then
    echo "Installing rclone..."
    apt install -y rclone
    echo "  Done — configure with: rclone config (add 'kisti' WebDAV remote)"
else
    echo "rclone already installed: $(rclone version | head -1)"
fi

echo ""
echo "=== System Config Complete ==="
echo ""
echo "Manual steps remaining:"
echo "  1. rclone config — add 'kisti' WebDAV remote for cloud.aldc.io"
echo "  2. WiFi hotspot — sudo bash scripts/jetson/wifi-hotspot.sh 'SSID' 'password'"
echo "  3. Reboot to activate: sudo reboot"
