#!/bin/bash
# Replace GDM with getty auto-login + startx → kisti-session
# Run once on the Jetson to switch from GDM to direct X startup.
# Saves ~500MB memory (no GNOME), boots straight into KiSTI.
set -e

SP="aldc1234"

echo "=== Disabling GDM ==="
echo "$SP" | sudo -S systemctl disable gdm3 2>/dev/null || true
echo "$SP" | sudo -S systemctl set-default multi-user.target

echo "=== Configuring getty auto-login on tty1 ==="
echo "$SP" | sudo -S mkdir -p /etc/systemd/system/getty@tty1.service.d/
echo "$SP" | sudo -S tee /etc/systemd/system/getty@tty1.service.d/override.conf > /dev/null << 'EOF'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin aldc --noclear %I 38400 linux
EOF
echo "$SP" | sudo -S systemctl daemon-reload

echo "=== Configuring .bash_profile for startx ==="
# Only add if not already present
if ! grep -q 'exec startx /usr/local/bin/kisti-session' ~/.bash_profile 2>/dev/null; then
    cat >> ~/.bash_profile << 'PROFILE'

# Auto-start KiSTI on tty1 (no display manager)
if [[ ! ${DISPLAY} && ${XDG_VTNR} == 1 ]]; then
    exec startx /usr/local/bin/kisti-session
fi
PROFILE
fi

echo "=== Updating kisti-session ==="
echo "$SP" | sudo -S cp ~/repos/kisti/scripts/kisti-session /usr/local/bin/kisti-session

echo "=== Done. Reboot to start KiSTI without GDM. ==="
echo "    SSH still works. To get a shell on tty1: Ctrl+Alt+F2"
echo "    To revert: sudo systemctl enable gdm3 && sudo systemctl set-default graphical.target"
