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
# Method 1: Xorg command line
_DISP=$(ps aux | grep '[X]org' | grep -oP ':\d+' | head -1)
# Method 2: lock files
if [ -z "$_DISP" ]; then
    for _lock in /tmp/.X*-lock; do
        [ -f "$_lock" ] || continue
        _pid=$(cat "$_lock" 2>/dev/null | tr -d ' ')
        if [ -n "$_pid" ] && kill -0 "$_pid" 2>/dev/null; then
            _num=$(echo "$_lock" | sed 's|/tmp/.X||;s|-lock||')
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

# --- Steal X auth cookie from GDM ---
# GDM's Xorg runs as uid 128 with its own Xauthority. We need that cookie.
_GDM_AUTH="/run/user/128/gdm/Xauthority"
if [ -f "$_GDM_AUTH" ] || echo "$SP" | sudo -S test -f "$_GDM_AUTH" 2>/dev/null; then
    echo "$SP" | sudo -S xauth -f "$_GDM_AUTH" extract - "$_DISP" 2>/dev/null | xauth merge - 2>/dev/null
    echo "$(date) Merged GDM X cookie for $_DISP" >> "$LOG"
fi

# Also check user-level auth
for _try in "/run/user/$(id -u)/gdm/Xauthority" "$HOME/.Xauthority"; do
    [ -f "$_try" ] && export XAUTHORITY="$_try" && break
done

# Allow local connections (now that we have the cookie)
xhost +local: 2>/dev/null || true

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
