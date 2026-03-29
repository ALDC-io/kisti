#!/bin/bash
# One-shot voice pipeline installer for Jetson
# Kills old KiSTI, installs sudoers + kisti-session, restarts GDM.
# Run: ssh -t aldc@192.168.22.131 'bash ~/repos/kisti/scripts/jetson_install_voice.sh'
set -e

echo "=== KiSTI Voice Pipeline Install ==="
KISTI_DIR="$HOME/repos/kisti"

# 1. Kill any running KiSTI
pkill -9 -f 'python3 main.py' 2>/dev/null && echo "Killed old KiSTI" || echo "No KiSTI running"
sleep 1

# 2. Install sudoers (one sudo password prompt covers everything)
SUDOERS="/etc/sudoers.d/kisti-aldc"
if [ ! -f "$SUDOERS" ]; then
    echo "Installing sudoers rule..."
    echo 'aldc ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart gdm3, /usr/bin/systemctl restart gdm*, /sbin/reboot, /usr/sbin/alsactl store *, /usr/bin/cp * /usr/local/bin/*' | sudo tee "$SUDOERS" > /dev/null
    sudo chmod 0440 "$SUDOERS"
    sudo visudo -cf "$SUDOERS" && echo "  Sudoers OK" || { echo "  SYNTAX ERROR"; sudo rm -f "$SUDOERS"; exit 1; }
else
    echo "Sudoers already installed"
fi

# 3. Install updated kisti-session (has HDMI PulseAudio pin fix)
echo "Installing kisti-session..."
sudo cp "$KISTI_DIR/scripts/kisti-session" /usr/local/bin/kisti-session
sudo chmod +x /usr/local/bin/kisti-session

# 4. Verify
diff <(cat /usr/local/bin/kisti-session) <(cat "$KISTI_DIR/scripts/kisti-session") > /dev/null && \
    echo "  kisti-session: matches repo (HDMI fix installed)" || \
    echo "  WARNING: kisti-session differs from repo!"

# 5. AccountsService — ensure GDM auto-logins to KiSTI session (not GNOME)
echo "Setting KiSTI as default session..."
sudo mkdir -p /etc/kisti
printf '[User]\nSession=kisti-session\nSystemAccount=false\n' | sudo tee /etc/kisti/accountsservice-aldc > /dev/null
printf '[User]\nSession=kisti-session\nSystemAccount=false\n' | sudo tee /var/lib/AccountsService/users/aldc > /dev/null
if [ -f "$KISTI_DIR/scripts/kisti-accountsservice.conf" ]; then
    sudo cp "$KISTI_DIR/scripts/kisti-accountsservice.conf" /etc/tmpfiles.d/
    sudo systemd-tmpfiles --create kisti-accountsservice.conf 2>/dev/null || true
fi
echo "  KiSTI session set as default"

# 6. Restart GDM → KiSTI auto-starts with new kisti-session
echo ""
echo "Restarting GDM..."
sudo systemctl restart gdm3
echo "Done. KiSTI will auto-launch with HDMI audio fix."
