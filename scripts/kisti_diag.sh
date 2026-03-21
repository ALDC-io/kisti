#!/bin/bash
# KiSTI Diagnostics — scans all hardware and speaks results
# Usage: bash scripts/kisti_diag.sh
# Requires: KiSTI app running (uses /tmp/kisti_say.txt for voice output)

SAY="/tmp/kisti_say.txt"

say() {
    # Wait for any previous line to be consumed
    for i in $(seq 1 60); do
        [ ! -f "$SAY" ] && break
        sleep 0.5
    done
    echo "$1" > "$SAY"
    # Wait for this line to be consumed + spoken
    for i in $(seq 1 60); do
        [ ! -f "$SAY" ] && break
        sleep 0.5
    done
    # Extra wait for audio playback to finish
    sleep $(echo "$1" | wc -w | awk '{print $1 * 0.12 + 1.5}')
}

say "Running full diagnostics."

# CPU
CPU_TEMP=$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null | awk '{printf "%.0f", $1/1000}')
CPU_CORES=$(nproc)
UPTIME=$(uptime -p | sed 's/up //')
say "Jetson Orin Nano. ${CPU_CORES} cores. CPU at ${CPU_TEMP} degrees. Up ${UPTIME}."

# Memory
MEM_TOTAL=$(free -m | awk '/Mem:/{print $2}')
MEM_USED=$(free -m | awk '/Mem:/{print $3}')
MEM_FREE=$(free -m | awk '/Mem:/{print $7}')
say "Memory: ${MEM_USED} of ${MEM_TOTAL} megabytes used. ${MEM_FREE} available."

# Storage
ROOT_FREE=$(df -h / | awk 'NR==2{print $4}')
DATA_FREE=$(df -h /data 2>/dev/null | awk 'NR==2{print $4}')
if [ -n "$DATA_FREE" ]; then
    say "Storage: root has ${ROOT_FREE} free. NVMe data drive has ${DATA_FREE} free."
else
    say "Storage: root has ${ROOT_FREE} free. NVMe not mounted."
fi

# GPU
if nvidia-smi &>/dev/null; then
    say "NVIDIA GPU detected. CUDA available."
else
    say "No GPU detected."
fi

# Network
if ping -c 1 -W 2 8.8.8.8 &>/dev/null; then
    IP=$(hostname -I | awk '{print $1}')
    SSID=$(nmcli -t -f active,ssid dev wifi | grep '^yes' | cut -d: -f2 2>/dev/null)
    if [ -n "$SSID" ]; then
        say "Network online. WiFi connected to ${SSID}. IP address ${IP}."
    else
        say "Network online. IP address ${IP}."
    fi
else
    say "ALERT_Network offline. No internet connectivity."
fi

# Ollama
if curl -s --max-time 3 http://localhost:11434/api/tags | python3 -c "import sys,json; m=json.load(sys.stdin).get('models',[]); print(m[0]['name'] if m else '')" 2>/dev/null | grep -q .; then
    MODEL=$(curl -s --max-time 3 http://localhost:11434/api/tags | python3 -c "import sys,json; m=json.load(sys.stdin).get('models',[]); print(m[0]['name'] if m else 'unknown')" 2>/dev/null)
    say "Ollama online. Model ${MODEL} loaded."
else
    say "ALERT_Ollama not responding."
fi

# Piper TTS
if [ -f /data/piper/piper ] && [ -f /data/piper/en_GB-alba-medium.onnx ]; then
    say "Piper voice engine online. Alba voice loaded."
else
    say "ALERT_Piper voice engine not found."
fi

# CAN Bus
if ip link show can0 &>/dev/null; then
    say "CAN bus interface detected."
else
    say "No CAN bus interface. Link ECU not connected."
fi

# USB Devices
USB_COUNT=$(lsusb | grep -v -i 'hub\|root' | wc -l)
if [ "$USB_COUNT" -gt 0 ]; then
    say "${USB_COUNT} USB devices connected."
    lsusb | grep -v -i 'hub\|root' | while read line; do
        DEV=$(echo "$line" | sed 's/.*ID [0-9a-f:]* //')
        echo "  USB: $DEV"
    done
else
    say "No USB devices detected."
fi

# Audio
AUDIO_OUT=$(aplay -l 2>/dev/null | grep -c 'card')
if [ "$AUDIO_OUT" -gt 0 ]; then
    say "Audio output available. ${AUDIO_OUT} devices."
else
    say "ALERT_No audio output detected."
fi

# Bluetooth
BT_PAIRED=$(bluetoothctl devices Paired 2>/dev/null | wc -l)
if [ "$BT_PAIRED" -gt 0 ]; then
    say "${BT_PAIRED} Bluetooth devices paired."
else
    say "No Bluetooth devices paired."
fi

# Display
DISPLAY_INFO=$(xrandr 2>/dev/null | grep ' connected' | head -1 | awk '{print $1, $3}')
if [ -n "$DISPLAY_INFO" ]; then
    say "Display connected: ${DISPLAY_INFO}."
fi

# DuckDB
if [ -f /data/duckdb/kisti.duckdb ]; then
    DB_SIZE=$(du -h /data/duckdb/kisti.duckdb | awk '{print $1}')
    say "DuckDB session store: ${DB_SIZE}."
else
    say "DuckDB not initialized."
fi

say "Diagnostics complete."
