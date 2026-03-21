#!/bin/bash
# KiSTI Jetson Orin Nano Setup Script
#
# Installs all AI dependencies on the Jetson:
# - Ollama (LLM inference)
# - Piper TTS (ARM64 binary + voice model)
# - DuckDB Python package
# - python-can (CAN bus library)
# - sounddevice (audio I/O)
# - numpy (signal processing)
#
# Run as: sudo -u aldc bash /path/to/jetson_setup.sh
# Requires: /data mounted (NVMe)

set -e

echo "=== KiSTI Jetson Setup ==="

# Check /data exists
if [ ! -d /data ]; then
    echo "ERROR: /data not mounted. Mount NVMe first."
    exit 1
fi

# Create data directories
mkdir -p /data/ollama /data/whisper /data/piper /data/sync_queue /data/duckdb /data/sessions
echo "Data directories created."

# --- Ollama ---
if ! command -v ollama &>/dev/null; then
    echo "Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
    echo "Ollama installed."
else
    echo "Ollama already installed: $(ollama --version 2>/dev/null)"
fi

# Configure Ollama to use NVMe for models
mkdir -p ~/.config/systemd/user
cat > /tmp/ollama-env.conf << 'EOF'
[Service]
Environment="OLLAMA_MODELS=/data/ollama"
EOF
sudo mkdir -p /etc/systemd/system/ollama.service.d/
sudo cp /tmp/ollama-env.conf /etc/systemd/system/ollama.service.d/override.conf
sudo systemctl daemon-reload
sudo systemctl restart ollama 2>/dev/null || true
echo "Ollama configured for /data/ollama"

# --- Piper TTS ---
PIPER_VERSION="2023.11.14-2"
PIPER_DIR="/data/piper"
if [ ! -f "$PIPER_DIR/piper" ]; then
    echo "Installing Piper TTS..."
    cd /tmp
    wget -q "https://github.com/rhasspy/piper/releases/download/${PIPER_VERSION}/piper_linux_aarch64.tar.gz"
    tar xzf piper_linux_aarch64.tar.gz -C "$PIPER_DIR" --strip-components=1
    rm piper_linux_aarch64.tar.gz
    chmod +x "$PIPER_DIR/piper"
    echo "Piper TTS installed."

    # Download voice model
    echo "Downloading Piper voice model (en_US-lessac-medium)..."
    wget -q -O "$PIPER_DIR/en_US-lessac-medium.onnx" \
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
    wget -q -O "$PIPER_DIR/en_US-lessac-medium.onnx.json" \
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"
    echo "Voice model downloaded."
else
    echo "Piper TTS already installed."
fi

# --- Python packages ---
echo "Installing Python packages..."
pip3 install --break-system-packages --quiet \
    duckdb \
    python-can \
    sounddevice \
    numpy \
    PySide6

echo "Python packages installed."

# --- Set Jetson to max performance ---
echo "Setting Jetson to max performance mode..."
sudo nvpmodel -m 0 2>/dev/null || echo "nvpmodel not available"
sudo jetson_clocks 2>/dev/null || echo "jetson_clocks not available"

# --- ALSA USB audio check ---
echo ""
echo "=== Audio devices ==="
aplay -l 2>/dev/null || echo "No playback devices found"
arecord -l 2>/dev/null || echo "No capture devices found"

echo ""
echo "=== Display ==="
xrandr 2>/dev/null || echo "No display (headless)"

echo ""
echo "=== GPU ==="
nvidia-smi 2>/dev/null | head -5 || echo "nvidia-smi not available"

# --- CAN bus interface ---
echo ""
echo "=== CAN Bus ==="
if ip link show can0 &>/dev/null; then
    sudo ip link set can0 up type can bitrate 1000000 2>/dev/null && \
        echo "CAN interface can0 up at 1 Mbps" || \
        echo "CAN interface can0 found but failed to bring up"
else
    echo "No CAN interface (can0 not found — connect USB-CAN adapter)"
fi

echo ""
echo "=== Setup Complete ==="
echo "Next steps:"
echo "  1. Pull LLM model: OLLAMA_MODELS=/data/ollama ollama pull llama3.2:3b"
echo "  2. Connect USB-CAN adapter"
echo "  3. Connect USB audio adapter"
echo "  4. Test: python3 main.py --platform offscreen"
