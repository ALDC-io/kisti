#!/bin/bash
# Tear down the KiSTI AP network and return the interface to NetworkManager.
set -uo pipefail

IFACE="${KISTI_AP_IFACE:-}"
if [ -z "$IFACE" ]; then
    IFACE=$(ls /sys/class/net | grep -E '^(wl|wlan)' | head -n1)
fi
[ -z "$IFACE" ] && exit 0

echo "kisti-ap-down: tearing down $IFACE"

iptables -t nat -D PREROUTING -i "$IFACE" -p tcp --dport 80 \
    -j REDIRECT --to-port 8080 2>/dev/null || true

ip addr flush dev "$IFACE" 2>/dev/null || true
nmcli device set "$IFACE" managed yes 2>/dev/null || true

echo "kisti-ap-down: done"
