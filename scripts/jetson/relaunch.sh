#!/bin/bash
# Relaunch KiSTI on the Jetson display — works with or without GDM
set -e

LOG="/tmp/kisti-session.log"
SP="aldc1234"

# Update system files
echo "$SP" | sudo -S cp ~/repos/kisti/scripts/kisti-session /usr/local/bin/kisti-session 2>/dev/null

# Kill existing KiSTI
pkill -9 -f 'python3 main.py' 2>/dev/null || true
sleep 1

# Find active X display from sockets
_DISP=""
_XORG_PID=$(pgrep -x Xorg 2>/dev/null | head -1)
if [ -n "$_XORG_PID" ]; then
    for _sock in /tmp/.X11-unix/X*; do
        [ -S "$_sock" ] || continue
        _num=$(basename "$_sock" | sed 's/X//')
        _DISP=":$_num"
        break
    done
fi

# No X server running — start one (getty+startx mode)
if [ -z "$_DISP" ]; then
    echo "No X server — starting via startx"
    cd ~/repos/kisti
    nohup startx /usr/local/bin/kisti-session > "$LOG" 2>&1 &
    disown
    echo "DEPLOYED — KiSTI via startx (PID $!)"
    exit 0
fi

export DISPLAY="$_DISP"

# Open display for local connections (GDM mode — Xorg runs as gdm user)
_GDM_AUTH="/run/user/128/gdm/Xauthority"
if echo "$SP" | sudo -S test -f "$_GDM_AUTH" 2>/dev/null; then
    echo "$SP" | sudo -S env DISPLAY="$_DISP" XAUTHORITY="$_GDM_AUTH" xhost +local: 2>/dev/null || true
fi

# Kill GNOME if present (GDM mode)
pkill -f gnome-shell 2>/dev/null || true
pkill -f gnome-session-binary 2>/dev/null || true
sleep 1

# Black background, no blanking
xsetroot -solid black 2>/dev/null || true
xset s off -dpms 2>/dev/null || true

# Launch KiSTI
cd ~/repos/kisti
echo "$(date) Relaunch: DISPLAY=$_DISP" > "$LOG"
nohup /usr/local/bin/kisti-session >> "$LOG" 2>&1 &
disown
echo "DEPLOYED — KiSTI on DISPLAY=$_DISP (PID $!)"
