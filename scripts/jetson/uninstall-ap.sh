#!/bin/bash
# Revert install-ap.sh — stops services, removes configs, restores backups.
set -uo pipefail

if [ "$EUID" -ne 0 ]; then
    echo "must run as root (use sudo)" >&2
    exit 1
fi

echo "stopping services..."
systemctl stop kisti-captive-portal kisti-ap-network hostapd dnsmasq 2>/dev/null || true
systemctl disable kisti-captive-portal kisti-ap-network 2>/dev/null || true

echo "removing units and configs..."
rm -f /etc/systemd/system/kisti-captive-portal.service
rm -f /etc/systemd/system/kisti-ap-network.service
rm -f /etc/dnsmasq.d/kisti.conf
rm -f /etc/avahi/services/kisti.service
rm -f /etc/default/kisti-ap

restore() {
    local path="$1"
    if [ -e "${path}.kisti-bak" ]; then
        mv -f "${path}.kisti-bak" "$path"
        echo "  restored $path"
    else
        rm -f "$path"
    fi
}
restore /etc/hostapd/hostapd.conf
restore /etc/default/hostapd

rm -rf /opt/kisti

systemctl daemon-reload
echo "KiSTI AP removed. Interface returns to NetworkManager on next boot."
