#!/bin/bash
# KiSTI Jetson Orin Nano Setup Script
#
# Installs ALL dependencies on the Jetson:
# - Ollama (LLM inference)
# - Piper TTS (ARM64 binary + voice model)
# - WhisperTRT (STT — PyTorch + torch2trt + openai-whisper + whisper_trt)
# - Python packages (DuckDB, python-can, PySide6, webrtcvad, etc.)
# - System config (disable conflicting kisti.service, install kisti-session)
#
# Run as: bash ~/repos/kisti/scripts/jetson_setup.sh
# Some steps require sudo (will prompt for password).
# Requires: /data mounted (NVMe)
#
# Idempotent — safe to re-run. Skips already-installed components.

set -e

KISTI_DIR="$(cd "$(dirname "$0")/.." && pwd)"
echo "=== KiSTI Jetson Setup ==="
echo "Repo: $KISTI_DIR"

# Check /data exists
if [ ! -d /data ]; then
    echo "ERROR: /data not mounted. Mount NVMe first."
    exit 1
fi

# Create data directories
mkdir -p /data/ollama /data/whisper /data/piper /data/sync_queue /data/duckdb /data/sessions
echo "Data directories created."

# ===================================================================
# 1. Ollama (LLM inference)
# ===================================================================
if ! command -v ollama &>/dev/null; then
    echo ""
    echo "--- Installing Ollama ---"
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

# ===================================================================
# 2. Piper TTS (offline voice synthesis)
# ===================================================================
PIPER_VERSION="2023.11.14-2"
PIPER_DIR="/data/piper"
if [ ! -f "$PIPER_DIR/piper" ]; then
    echo ""
    echo "--- Installing Piper TTS ---"
    cd /tmp
    wget -q "https://github.com/rhasspy/piper/releases/download/${PIPER_VERSION}/piper_linux_aarch64.tar.gz"
    tar xzf piper_linux_aarch64.tar.gz -C "$PIPER_DIR" --strip-components=1
    rm piper_linux_aarch64.tar.gz
    chmod +x "$PIPER_DIR/piper"

    echo "Downloading Piper voice model (en_US-lessac-medium)..."
    wget -q -O "$PIPER_DIR/en_US-lessac-medium.onnx" \
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
    wget -q -O "$PIPER_DIR/en_US-lessac-medium.onnx.json" \
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"
    echo "Piper TTS installed."
else
    echo "Piper TTS already installed."
fi

# ===================================================================
# 3. WhisperTRT (GPU-accelerated speech-to-text)
# ===================================================================
# Chain: PyTorch → openai-whisper → torch2trt → whisper_trt → build TRT engine
# Total ~3 GB disk. First-run engine build takes ~5-10 min on Orin Nano.

TORCH_INDEX="https://pypi.jetson-ai-lab.io/jp6/cu126"

# 3a. PyTorch (Jetson-specific CUDA wheel)
if ! python3 -c "import torch; print(f'PyTorch {torch.__version__} CUDA={torch.cuda.is_available()}')" 2>/dev/null; then
    echo ""
    echo "--- Installing PyTorch (Jetson CUDA wheel) ---"
    echo "This is ~2 GB, may take a few minutes..."
    pip3 install torch torchvision --index-url="$TORCH_INDEX" 2>&1 || {
        echo "WARN: jetson-ai-lab.io index failed, trying .dev mirror..."
        pip3 install torch torchvision --index-url="https://pypi.jetson-ai-lab.dev/jp6/cu126" 2>&1
    }
    python3 -c "import torch; print(f'  PyTorch {torch.__version__} CUDA={torch.cuda.is_available()}')"
else
    python3 -c "import torch; print(f'PyTorch {torch.__version__} already installed (CUDA={torch.cuda.is_available()})')"
fi

# 3b. openai-whisper (model definitions + tokenizer)
if ! python3 -c "import whisper" 2>/dev/null; then
    echo ""
    echo "--- Installing openai-whisper ---"
    pip3 install openai-whisper 2>&1
    echo "openai-whisper installed."
else
    echo "openai-whisper already installed."
fi

# 3c. torch2trt (NVIDIA's PyTorch → TensorRT converter)
if ! python3 -c "import torch2trt" 2>/dev/null; then
    echo ""
    echo "--- Installing torch2trt from source ---"
    cd /tmp
    rm -rf torch2trt
    git clone https://github.com/NVIDIA-AI-IOT/torch2trt.git
    cd torch2trt
    python3 setup.py install --user 2>&1
    cd /tmp && rm -rf torch2trt
    echo "torch2trt installed."
else
    echo "torch2trt already installed."
fi

# 3d. onnxruntime + onnx + onnx_graphsurgeon (needed for TRT engine build)
if ! python3 -c "import onnxruntime" 2>/dev/null; then
    echo ""
    echo "--- Installing onnxruntime ---"
    pip3 install onnxruntime 2>&1
    echo "onnxruntime installed."
else
    echo "onnxruntime already installed."
fi
# onnx_graphsurgeon requires onnx<1.17 (1.17+ removed float32_to_bfloat16)
if ! python3 -c "import onnx_graphsurgeon" 2>/dev/null; then
    echo ""
    echo "--- Installing onnx + onnx_graphsurgeon (pinned for TRT compat) ---"
    pip3 install 'onnx<1.17' 'onnx_graphsurgeon==0.5.2' 2>&1
    echo "onnx + onnx_graphsurgeon installed."
else
    echo "onnx_graphsurgeon already installed."
fi

# 3e. whisper_trt (NVIDIA's TensorRT-optimized Whisper)
if ! python3 -c "from whisper_trt import load_trt_model" 2>/dev/null; then
    echo ""
    echo "--- Installing whisper_trt from source ---"
    cd /tmp
    rm -rf whisper_trt
    git clone https://github.com/NVIDIA-AI-IOT/whisper_trt.git
    cd whisper_trt
    pip3 install -e . 2>&1
    echo "whisper_trt installed."
else
    echo "whisper_trt already installed."
fi

# 3f. Build TRT engine (one-time conversion, ~5-10 min)
if [ ! -f /data/whisper/base.en ]; then
    echo ""
    echo "--- Building WhisperTRT engine (base.en) ---"
    echo "This converts the Whisper model to TensorRT. Takes ~5-10 min..."
    mkdir -p /data/whisper
    python3 -c "
from whisper.model import MultiHeadAttention
MultiHeadAttention.use_sdpa = False  # PyTorch 2.8+ compat
from whisper_trt import load_trt_model
model = load_trt_model('base.en', path='/data/whisper/base.en')
print('WhisperTRT engine built successfully!')
" 2>&1
    echo "TRT engine saved to /data/whisper/base.en"
else
    echo "WhisperTRT engine already exists at /data/whisper/base.en"
fi

# ===================================================================
# 4. Python packages (core KiSTI deps)
# ===================================================================
echo ""
echo "--- Installing Python packages ---"
pip3 install \
    duckdb \
    python-can \
    sounddevice \
    numpy \
    PySide6 \
    webrtcvad \
    psutil \
    2>&1
echo "Python packages installed."

# ===================================================================
# 5. System config (process management)
# ===================================================================
echo ""
echo "--- System configuration ---"

# Disable kisti.service if enabled (conflicts with GDM kisti-session)
if systemctl is-enabled kisti.service &>/dev/null; then
    echo "Disabling kisti.service (GDM kisti-session is the intended startup)..."
    sudo systemctl stop kisti.service 2>/dev/null || true
    sudo systemctl disable kisti.service
    echo "  kisti.service disabled."
else
    echo "kisti.service already disabled (good)."
fi

# Install/update kisti-session script
if [ -f "$KISTI_DIR/scripts/kisti-session" ]; then
    echo "Installing kisti-session to /usr/local/bin/..."
    sudo cp "$KISTI_DIR/scripts/kisti-session" /usr/local/bin/kisti-session
    sudo chmod +x /usr/local/bin/kisti-session
    echo "  kisti-session updated."
fi

# Allow passwordless sudo for GDM restart + reboot (remote management)
SUDOERS_FILE="/etc/sudoers.d/kisti-aldc"
if [ ! -f "$SUDOERS_FILE" ]; then
    echo "Installing sudoers rule for remote GDM/reboot management..."
    echo 'aldc ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart gdm3, /usr/bin/systemctl restart gdm*, /sbin/reboot, /usr/sbin/alsactl store *' | sudo tee "$SUDOERS_FILE" > /dev/null
    sudo chmod 0440 "$SUDOERS_FILE"
    sudo visudo -cf "$SUDOERS_FILE" && echo "  Sudoers rule installed." || { echo "  Sudoers syntax error — removing."; sudo rm -f "$SUDOERS_FILE"; }
else
    echo "Sudoers rule already installed."
fi

# Install desktop entry if missing
if [ ! -f /usr/share/xsessions/kisti-session.desktop ] && [ -f "$KISTI_DIR/scripts/kisti-session.desktop" ]; then
    echo "Installing kisti-session.desktop..."
    sudo cp "$KISTI_DIR/scripts/kisti-session.desktop" /usr/share/xsessions/
    echo "  Desktop entry installed."
fi

# ===================================================================
# 6. Performance + hardware check
# ===================================================================
echo ""
echo "--- Setting max performance mode ---"
sudo nvpmodel -m 0 2>/dev/null || echo "nvpmodel not available"
sudo jetson_clocks 2>/dev/null || echo "jetson_clocks not available"

echo ""
echo "=== Hardware Check ==="

echo "Audio playback:"
aplay -l 2>/dev/null | grep -E 'card|device' || echo "  No playback devices"

echo "Audio capture:"
arecord -l 2>/dev/null | grep -E 'card|device' || echo "  No capture devices"

# Set USB mic gain to 30% — 100% clips and Whisper can't transcribe distorted audio
MIC_CARD=$(arecord -l 2>/dev/null | grep -i 'USB.*MIC\|USB.*Audio\|USB.*Adapter' | head -1 | grep -oP 'card \K\d+' || true)
if [ -n "$MIC_CARD" ]; then
    amixer -c "$MIC_CARD" cset numid=3 30 2>/dev/null && \
        echo "  USB mic (card $MIC_CARD) gain set to 30%" || \
        echo "  USB mic gain set failed (non-fatal)"
fi

echo "Display:"
xrandr 2>/dev/null | head -3 || echo "  No display (headless)"

echo "GPU:"
nvidia-smi 2>/dev/null | head -5 || echo "  nvidia-smi not available"

if ip link show can0 &>/dev/null; then
    sudo ip link set can0 up type can bitrate 1000000 2>/dev/null && \
        echo "CAN: can0 up at 1 Mbps" || \
        echo "CAN: can0 found but failed to bring up"
else
    echo "CAN: no can0 (connect USB-CAN adapter)"
fi

# ===================================================================
# Summary
# ===================================================================
echo ""
echo "=== Setup Complete ==="
echo ""
echo "Installed:"
python3 -c "import torch; print(f'  PyTorch {torch.__version__} (CUDA={torch.cuda.is_available()})')" 2>/dev/null || echo "  PyTorch: NOT INSTALLED"
python3 -c "import whisper; print('  openai-whisper: OK (STT via CUDA)')" 2>/dev/null || echo "  openai-whisper: NOT INSTALLED"
python3 -c "from whisper_trt import load_trt_model; print('  WhisperTRT: OK (available but not used — CUDA conflict with Ollama)')" 2>/dev/null || echo "  WhisperTRT: not installed (not needed)"
python3 -c "import torch2trt; print('  torch2trt: OK')" 2>/dev/null || echo "  torch2trt: not installed (not needed)"
echo "  Ollama: $(ollama --version 2>/dev/null || echo 'not found')"
[ -f /data/piper/piper ] && echo "  Piper TTS: OK" || echo "  Piper TTS: NOT INSTALLED"
echo ""
echo "Restarting GDM to launch KiSTI session..."
sudo systemctl restart gdm3
echo "GDM restarted — KiSTI should auto-login and launch."
echo ""
echo "Manual steps if needed:"
echo "  1. Pull LLM: OLLAMA_MODELS=/data/ollama ollama pull llama3.2:3b"
echo "  2. Run system config: sudo bash $KISTI_DIR/scripts/jetson/install-system.sh"
echo "  3. Test: cd $KISTI_DIR && python3 main.py --platform offscreen"
