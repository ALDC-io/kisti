#!/bin/bash
# Bring up the KiSTI AP network on the wireless interface:
#   - take wlan from NetworkManager
#   - assign static IP 192.168.42.1
#   - redirect inbound HTTP (port 80) to the captive portal on 8080
#
# Invoked by /etc/systemd/system/kisti-ap-network.service.
set -euo pipefail

IFACE="${KISTI_AP_IFACE:-}"
if [ -z "$IFACE" ]; then
    # Pick the first wireless interface
    IFACE=$(ls /sys/class/net | grep -E '^(wl|wlan)' | head -n1)
fi
if [ -z "$IFACE" ]; then
    echo "kisti-ap-up: no wireless interface found" >&2
    exit 1
fi

AP_IP="192.168.42.1"
AP_PREFIX="24"

echo "kisti-ap-up: configuring $IFACE as $AP_IP/$AP_PREFIX"

# Release from NetworkManager so hostapd can drive it
nmcli device set "$IFACE" managed no 2>/dev/null || true

# Static IP
ip addr flush dev "$IFACE" || true
ip addr add "${AP_IP}/${AP_PREFIX}" dev "$IFACE"
ip link set "$IFACE" up

# Redirect HTTP traffic on the AP interface to the captive portal.
# Scoped to $IFACE — Jetson's own outbound HTTP is unaffected.
if ! iptables -t nat -C PREROUTING -i "$IFACE" -p tcp --dport 80 \
        -j REDIRECT --to-port 8080 2>/dev/null; then
    iptables -t nat -A PREROUTING -i "$IFACE" -p tcp --dport 80 \
        -j REDIRECT --to-port 8080
fi

echo "kisti-ap-up: done"
