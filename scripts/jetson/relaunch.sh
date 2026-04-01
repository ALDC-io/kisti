#!/bin/bash
# Relaunch KiSTI on the Jetson display — runs ON the Jetson (via SSH or locally)
# Handles: find display, steal X auth from GDM, kill GNOME, launch fullscreen
set -e

LOG="/tmp/kisti-session.log"
SP="aldc1234"

# --- Update system files ---
echo "$SP" | sudo -S cp ~/repos/kisti/scripts/kisti-session /usr/local/bin/kisti-session 2>/dev/null
echo "$SP" | sudo -S cp ~/repos/kisti/scripts/jetson/kisti-session-user /var/lib/AccountsService/users/aldc 2>/dev/null
echo "$SP" | sudo -S cp ~/repos/kisti/scripts/jetson/gdm-custom.conf /etc/gdm3/custom.conf 2>/dev/null

# --- Kill existing KiSTI ---
pkill -9 -f 'python3 main.py' 2>/dev/null || true
sleep 1

# --- Find the X display ---
# Method 1: X11 unix sockets (most reliable — Xorg creates these)
_XORG_PID=$(pgrep -x Xorg 2>/dev/null | head -1)
_DISP=""
if [ -n "$_XORG_PID" ]; then
    for _sock in /tmp/.X11-unix/X*; do
        [ -S "$_sock" ] || continue
        _num=$(basename "$_sock" | sed 's/X//')
        # Prefer lowest display number owned by the running Xorg
        if [ -z "$_DISP" ]; then
            _DISP=":$_num"
        fi
    done
fi

if [ -z "$_DISP" ]; then
    echo "No X display found — restarting GDM"
    echo "$SP" | sudo -S systemctl restart gdm
    sleep 5
    exec "$0"  # retry once after GDM restart
fi

export DISPLAY="$_DISP"

# --- Open X display for local users ---
# Xorg runs as root with GDM's auth. Use sudo to allow local connections.
_GDM_AUTH="/run/user/128/gdm/Xauthority"
echo "$SP" | sudo -S env DISPLAY="$_DISP" XAUTHORITY="$_GDM_AUTH" xhost +local: 2>/dev/null || true
echo "$(date) xhost +local: on $_DISP via GDM auth" >> "$LOG"

# --- Kill GNOME shell (we're taking over) ---
pkill -f gnome-shell 2>/dev/null || true
pkill -f gnome-session 2>/dev/null || true
sleep 1

# --- Black background, no blanking ---
xsetroot -solid black 2>/dev/null || true
xset s off -dpms 2>/dev/null || true

# --- Launch kisti-session ---
cd ~/repos/kisti
echo "$(date) Relaunch: DISPLAY=$_DISP" > "$LOG"
nohup /usr/local/bin/kisti-session >> "$LOG" 2>&1 &
disown
echo "DEPLOYED — KiSTI on DISPLAY=$_DISP (PID $!)"
