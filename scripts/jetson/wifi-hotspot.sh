#!/bin/bash
# Add iPhone hotspot as a saved WiFi connection.
# Usage: sudo bash wifi-hotspot.sh "SSID" "password"
#
# Priority 10 = preferred over home WiFi (priority 5).
# Jetson auto-connects when hotspot is in range.

set -e

SSID="${1:?Usage: wifi-hotspot.sh SSID PASSWORD}"
PASSWORD="${2:?Usage: wifi-hotspot.sh SSID PASSWORD}"
IFACE="wlP1p1s0"

nmcli connection add \
    type wifi \
    con-name "mobile-hotspot" \
    ifname "$IFACE" \
    ssid "$SSID" \
    wifi-sec.key-mgmt wpa-psk \
    wifi-sec.psk "$PASSWORD" \
    connection.autoconnect yes \
    connection.autoconnect-priority 10

echo "Hotspot '$SSID' added (priority 10, auto-connect)"
