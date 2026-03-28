#!/bin/bash
# Install KiSTI minimal X session for GDM
#
# After install, select "KiSTI" from the gear icon on GDM login screen.
# To go back to GNOME, select "Ubuntu" at next login.
#
# Run as: sudo bash scripts/install-session.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Installing KiSTI session..."

# Install session script
cp "$SCRIPT_DIR/kisti-session" /usr/local/bin/kisti-session
chmod +x /usr/local/bin/kisti-session

# Install GDM session descriptor
cp "$SCRIPT_DIR/kisti-session.desktop" /usr/share/xsessions/kisti-session.desktop

# Allow passwordless CAN interface up (for session script)
if ! grep -q "can0 up" /etc/sudoers.d/kisti 2>/dev/null; then
    echo "aldc ALL=(root) NOPASSWD: /sbin/ip link set can0 up *" > /etc/sudoers.d/kisti
    chmod 440 /etc/sudoers.d/kisti
    echo "Sudoers rule added for CAN interface."
fi

echo ""
echo "KiSTI session installed."
echo "  - Log out and select 'KiSTI' from the GDM gear icon"
echo "  - To revert: select 'Ubuntu' at next login"
echo "  - Session log: /tmp/kisti-session.log"
