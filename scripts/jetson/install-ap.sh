#!/bin/bash
# Install the KiSTI WiFi access point + captive portal + Bonjour stack.
#
# Idempotent — safe to re-run. Backs up any pre-existing files to
# /etc/<file>.kisti-bak before overwriting.
#
# Usage:
#   sudo bash install-ap.sh                       # interactive
#   sudo KISTI_PASSPHRASE='secret123' bash install-ap.sh
#
# After install:
#   sudo systemctl start kisti-ap-network kisti-captive-portal hostapd dnsmasq avahi-daemon
#   Phone joins "KiSTI" WiFi, browses to http://kisti.local:8080/v1/health
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT_DIR="$REPO_DIR/scripts/jetson"

if [ "$EUID" -ne 0 ]; then
    echo "must run as root (use sudo)" >&2
    exit 1
fi

# --- 1. Resolve interface ---------------------------------------------------
IFACE="${KISTI_AP_IFACE:-}"
if [ -z "$IFACE" ]; then
    for dev in /sys/class/net/wl*; do
        [ -e "$dev" ] || continue
        IFACE=$(basename "$dev")
        break
    done
fi
if [ -z "$IFACE" ]; then
    echo "no wireless interface found; set KISTI_AP_IFACE=<name> and retry" >&2
    exit 1
fi
echo "using wireless interface: $IFACE"

# --- 2. Resolve passphrase --------------------------------------------------
PASSPHRASE="${KISTI_PASSPHRASE:-}"
if [ -z "$PASSPHRASE" ]; then
    read -rsp "KiSTI WiFi passphrase (min 8 chars): " PASSPHRASE
    echo
fi
if [ "${#PASSPHRASE}" -lt 8 ]; then
    echo "passphrase must be at least 8 characters" >&2
    exit 1
fi

# --- 3. Install packages ----------------------------------------------------
echo "installing packages..."
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
    hostapd dnsmasq avahi-daemon iptables

# Unmask hostapd — Ubuntu ships it masked by default
systemctl unmask hostapd 2>/dev/null || true

# --- 4. Layout target tree --------------------------------------------------
install -d -m 755 /opt/kisti
install -m 755 "$SCRIPT_DIR/kisti-ap-up.sh"   /opt/kisti/kisti-ap-up.sh
install -m 755 "$SCRIPT_DIR/kisti-ap-down.sh" /opt/kisti/kisti-ap-down.sh
install -m 644 "$SCRIPT_DIR/captive_portal.py" /opt/kisti/captive_portal.py

# --- 5. Write hostapd config with substitutions -----------------------------
backup_if_exists() {
    local path="$1"
    if [ -e "$path" ] && [ ! -e "${path}.kisti-bak" ]; then
        cp -a "$path" "${path}.kisti-bak"
        echo "  backed up $path -> ${path}.kisti-bak"
    fi
}

backup_if_exists /etc/hostapd/hostapd.conf
mkdir -p /etc/hostapd
sed -e "s|{{IFACE}}|$IFACE|g" \
    -e "s|{{PASSPHRASE}}|$PASSPHRASE|g" \
    "$SCRIPT_DIR/hostapd-kisti.conf" \
    > /etc/hostapd/hostapd.conf
chmod 600 /etc/hostapd/hostapd.conf

# Point the hostapd systemd unit at our config (Debian/Ubuntu convention)
if [ -f /etc/default/hostapd ]; then
    backup_if_exists /etc/default/hostapd
fi
echo 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' > /etc/default/hostapd

# --- 6. Write dnsmasq drop-in (don't replace main config) -------------------
mkdir -p /etc/dnsmasq.d
sed -e "s|{{IFACE}}|$IFACE|g" \
    "$SCRIPT_DIR/dnsmasq-kisti.conf" \
    > /etc/dnsmasq.d/kisti.conf

# --- 7. Avahi service advertisement -----------------------------------------
install -d -m 755 /etc/avahi/services
install -m 644 "$SCRIPT_DIR/avahi-kisti.service.xml" \
    /etc/avahi/services/kisti.service

# --- 8. Persist chosen interface for the up/down scripts --------------------
echo "KISTI_AP_IFACE=$IFACE" > /etc/default/kisti-ap
chmod 644 /etc/default/kisti-ap

# --- 9. Install systemd units -----------------------------------------------
install -m 644 "$SCRIPT_DIR/kisti-ap-network.service" \
    /etc/systemd/system/kisti-ap-network.service
install -m 644 "$SCRIPT_DIR/kisti-captive-portal.service" \
    /etc/systemd/system/kisti-captive-portal.service

systemctl daemon-reload
systemctl enable kisti-ap-network.service kisti-captive-portal.service \
    hostapd.service dnsmasq.service avahi-daemon.service

cat <<EOF

KiSTI AP installed.

Interface : $IFACE
SSID      : KiSTI
Gateway   : 192.168.42.1
Bonjour   : _kisti._tcp on port 8080 -> http://kisti.local:8080

Start now:
  sudo systemctl start kisti-ap-network kisti-captive-portal \\
                       hostapd dnsmasq avahi-daemon

Verify:
  systemctl status hostapd dnsmasq kisti-captive-portal
  iw dev $IFACE info        # should show "type AP"
  curl http://192.168.42.1:8080/v1/health

To revert: sudo bash $SCRIPT_DIR/uninstall-ap.sh
EOF
