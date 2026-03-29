#!/bin/bash
# KiSTI Voice Pipeline Validation Script
#
# Tests each component of the voice pipeline independently, then end-to-end.
# Run on the Jetson directly. Designed for pre-tune-session confidence.
#
# Usage: bash ~/repos/kisti/scripts/voice_test.sh [--all|--mic|--stt|--tts|--hdmi|--pipeline]
#        Default: --all
#
# Exit codes: 0 = all passed, 1 = one or more failures

set -o pipefail

KISTI_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TMP="/tmp/kisti_voice_test"
mkdir -p "$TMP"

PASS=0
FAIL=0
WARN=0

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

pass() { echo -e "  ${GREEN}PASS${NC} $1"; ((PASS++)); }
fail() { echo -e "  ${RED}FAIL${NC} $1"; ((FAIL++)); }
warn() { echo -e "  ${YELLOW}WARN${NC} $1"; ((WARN++)); }
info() { echo -e "  ${CYAN}INFO${NC} $1"; }
header() { echo -e "\n${BOLD}=== $1 ===${NC}"; }

# ===================================================================
# Detect USB mic
# ===================================================================
detect_mic() {
    MIC_CARD=$(arecord -l 2>/dev/null | grep -i 'USB.*MIC\|USB.*Audio\|USB.*Adapter' | head -1 | grep -oP 'card \K\d+' || true)
    if [ -n "$MIC_CARD" ]; then
        MIC_DEVICE="plughw:${MIC_CARD},0"
        info "USB mic detected: card $MIC_CARD → $MIC_DEVICE"
    else
        MIC_DEVICE=""
        fail "No USB mic found"
    fi
}

# ===================================================================
# Test 1: Microphone capture + RMS level check
# ===================================================================
test_mic() {
    header "Test 1: Microphone Capture"
    detect_mic
    [ -z "$MIC_DEVICE" ] && return

    # Set gain to 30%
    amixer -c "$MIC_CARD" cset numid=3 30 >/dev/null 2>&1 || warn "Could not set mic gain"
    GAIN=$(amixer -c "$MIC_CARD" cget numid=3 2>/dev/null | grep -oP ': values=\K\d+' || echo "?")
    info "Mic gain: $GAIN%"

    # Record 3 seconds
    info "Recording 3 seconds... (speak or tap the mic)"
    WAV="$TMP/mic_test.wav"
    arecord -D "$MIC_DEVICE" -f S16_LE -r 16000 -c 1 -d 3 "$WAV" 2>/dev/null
    if [ ! -f "$WAV" ] || [ ! -s "$WAV" ]; then
        fail "arecord produced no output"
        return
    fi
    pass "arecord captured audio ($(stat -c%s "$WAV") bytes)"

    # Check RMS level with Python
    RMS_RESULT=$(python3 -c "
import wave, struct, math
with wave.open('$WAV', 'rb') as wf:
    frames = wf.readframes(wf.getnframes())
    n = len(frames) // 2
    if n == 0:
        print('ERROR 0 0')
    else:
        total = sum(struct.unpack_from('<h', frames, i*2)[0]**2 for i in range(n))
        rms = math.sqrt(total / n)
        peak = max(abs(struct.unpack_from('<h', frames, i*2)[0]) for i in range(n))
        print(f'OK {rms:.0f} {peak}')
" 2>&1)

    STATUS=$(echo "$RMS_RESULT" | awk '{print $1}')
    RMS=$(echo "$RMS_RESULT" | awk '{print $2}')
    PEAK=$(echo "$RMS_RESULT" | awk '{print $3}')

    if [ "$STATUS" != "OK" ]; then
        fail "RMS analysis failed: $RMS_RESULT"
        return
    fi

    info "RMS: $RMS, Peak: $PEAK (max 32767)"

    # RMS < 50 = dead silence (mic not working)
    # RMS > 10000 = clipping (gain too high)
    # Peak = 32767 = hard clipping
    if [ "$PEAK" -eq 32767 ]; then
        fail "CLIPPING detected (peak=32767). Reduce mic gain below 30%"
    elif [ "${RMS%.*}" -lt 50 ]; then
        warn "Very low RMS ($RMS) — mic may not be capturing. Try speaking louder or check connection"
    elif [ "${RMS%.*}" -gt 10000 ]; then
        warn "High RMS ($RMS) — possible clipping. Consider reducing gain"
    else
        pass "Audio levels healthy (RMS=$RMS, Peak=$PEAK)"
    fi
}

# ===================================================================
# Test 2: STT (Whisper) transcription
# ===================================================================
test_stt() {
    header "Test 2: Speech-to-Text (Whisper)"

    # Check Whisper is importable with CUDA
    WHISPER_CHECK=$(python3 -c "
import torch
import whisper
device = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f'OK {device}')
" 2>&1)

    if echo "$WHISPER_CHECK" | grep -q "^OK"; then
        DEVICE=$(echo "$WHISPER_CHECK" | awk '{print $2}')
        pass "Whisper importable, device=$DEVICE"
        [ "$DEVICE" = "cpu" ] && warn "Running on CPU — will be slow"
    else
        fail "Cannot import Whisper: $WHISPER_CHECK"
        return
    fi

    # Generate a known test phrase via TTS, then transcribe it
    # This tests STT without requiring the user to speak
    info "Generating test audio via Piper..."
    TEST_PHRASE="Hello, this is a voice pipeline test"
    TEST_WAV="$TMP/stt_test.wav"

    if [ -f /data/piper/piper ] && [ -f /data/piper/en_US-lessac-medium.onnx ]; then
        echo "$TEST_PHRASE" | /data/piper/piper \
            --model /data/piper/en_US-lessac-medium.onnx \
            --output_file "$TEST_WAV" 2>/dev/null

        if [ ! -f "$TEST_WAV" ] || [ ! -s "$TEST_WAV" ]; then
            warn "Piper failed to generate test audio — skipping STT accuracy test"
            return
        fi
    else
        warn "Piper not available — skipping STT accuracy test"
        return
    fi

    # Transcribe
    info "Transcribing with Whisper tiny.en..."
    STT_RESULT=$(python3 -c "
import time, sys
sys.path.insert(0, '$KISTI_DIR')
from voice.stt_engine import STTEngine
engine = STTEngine()
engine.start()
result = engine.transcribe_file('$TEST_WAV')
engine.stop()
print(f'{result.latency_s:.2f}|{result.text}')
" 2>&1)

    if echo "$STT_RESULT" | grep -q "|"; then
        LATENCY=$(echo "$STT_RESULT" | cut -d'|' -f1)
        TEXT=$(echo "$STT_RESULT" | cut -d'|' -f2-)
        info "Transcription: '$TEXT' (${LATENCY}s)"

        if [ -z "$TEXT" ]; then
            fail "Empty transcription (hallucination filter may be too aggressive)"
        elif echo "$TEXT" | grep -iq "voice.*pipeline\|test\|hello"; then
            pass "STT transcription matches expected content"
        else
            warn "Transcription doesn't match expected phrase — got: '$TEXT'"
        fi
    else
        fail "STT transcription failed: $STT_RESULT"
    fi

    # Also test with live mic recording if available
    WAV="$TMP/mic_test.wav"
    if [ -f "$WAV" ] && [ -s "$WAV" ]; then
        info "Also transcribing live mic recording..."
        LIVE_STT=$(python3 -c "
import sys
sys.path.insert(0, '$KISTI_DIR')
from voice.stt_engine import STTEngine
engine = STTEngine()
engine.start()
result = engine.transcribe_file('$TMP/mic_test.wav')
engine.stop()
print(f'{result.latency_s:.2f}|{result.text}')
" 2>&1)
        LIVE_TEXT=$(echo "$LIVE_STT" | cut -d'|' -f2-)
        LIVE_LAT=$(echo "$LIVE_STT" | cut -d'|' -f1)
        info "Live mic STT: '$LIVE_TEXT' (${LIVE_LAT}s)"
    fi
}

# ===================================================================
# Test 3: TTS (Piper) audio generation
# ===================================================================
test_tts() {
    header "Test 3: Text-to-Speech (Piper)"

    # Check Piper binary
    if [ ! -f /data/piper/piper ]; then
        fail "Piper binary not found at /data/piper/piper"
        return
    fi
    pass "Piper binary exists"

    # Check voice models
    for model in en_US-lessac-medium en_US-danny-low; do
        if [ -f "/data/piper/${model}.onnx" ]; then
            pass "Voice model: $model"
        else
            warn "Voice model missing: $model"
        fi
    done

    # Generate test audio
    TEST_TEXT="Systems nominal. Boost pressure at fourteen pounds. Oil temp steady."
    TTS_WAV="$TMP/tts_test.wav"

    info "Generating TTS audio..."
    START_MS=$(date +%s%N)
    echo "$TEST_TEXT" | /data/piper/piper \
        --model /data/piper/en_US-lessac-medium.onnx \
        --output_file "$TTS_WAV" 2>/dev/null
    END_MS=$(date +%s%N)

    if [ ! -f "$TTS_WAV" ] || [ ! -s "$TTS_WAV" ]; then
        fail "Piper produced no output"
        return
    fi

    SIZE=$(stat -c%s "$TTS_WAV")
    LATENCY_MS=$(( (END_MS - START_MS) / 1000000 ))
    pass "TTS generated: $SIZE bytes in ${LATENCY_MS}ms"

    # Validate WAV format
    WAV_INFO=$(python3 -c "
import wave
with wave.open('$TTS_WAV', 'rb') as wf:
    print(f'{wf.getnchannels()} {wf.getsampwidth()} {wf.getframerate()} {wf.getnframes()}')
" 2>&1)

    CHANNELS=$(echo "$WAV_INFO" | awk '{print $1}')
    SAMPWIDTH=$(echo "$WAV_INFO" | awk '{print $2}')
    RATE=$(echo "$WAV_INFO" | awk '{print $3}')
    FRAMES=$(echo "$WAV_INFO" | awk '{print $4}')

    if [ "$CHANNELS" = "1" ] && [ "$SAMPWIDTH" = "2" ]; then
        DURATION_S=$(python3 -c "print(f'{$FRAMES / $RATE:.1f}')")
        pass "WAV format: mono 16-bit ${RATE}Hz, ${DURATION_S}s"
    else
        fail "Unexpected WAV format: channels=$CHANNELS, sampwidth=$SAMPWIDTH"
    fi

    # Test AudioPlayer's danny-low voice too
    DANNY_WAV="$TMP/tts_danny.wav"
    if [ -f "/data/piper/en_US-danny-low.onnx" ]; then
        echo "Ready to roll." | /data/piper/piper \
            --model /data/piper/en_US-danny-low.onnx \
            --output_file "$DANNY_WAV" 2>/dev/null
        if [ -f "$DANNY_WAV" ] && [ -s "$DANNY_WAV" ]; then
            pass "Danny-low voice also works (AudioPlayer path)"
        else
            warn "Danny-low voice failed to generate"
        fi
    fi
}

# ===================================================================
# Test 4: HDMI audio playback
# ===================================================================
test_hdmi() {
    header "Test 4: HDMI Audio Playback"

    # Check HDMI audio device
    if aplay -l 2>/dev/null | grep -qi 'HDMI\|HDA'; then
        pass "HDMI audio device found"
    else
        warn "No HDMI audio device detected in aplay -l"
    fi

    # PulseAudio MUST be running — Jetson HDA resets pin-ctl without it
    if pulseaudio --check 2>/dev/null; then
        pass "PulseAudio running (required for HDMI pin-ctl)"
    else
        warn "PulseAudio not running — HDMI audio will not work. Starting..."
        pulseaudio --start --exit-idle-time=-1 2>/dev/null || true
        sleep 2
        if pulseaudio --check 2>/dev/null; then
            pass "PulseAudio started successfully"
        else
            fail "Cannot start PulseAudio"
        fi
    fi

    # Generate a 440Hz test tone
    TONE_WAV="$TMP/tone_440hz.wav"
    python3 -c "
import wave, struct, math
sr = 22050
duration = 2.0
# 500ms silence (DAC wake) + 1.5s 440Hz tone
silence = int(sr * 0.5)
tone = int(sr * 1.5)
samples = []
for i in range(silence):
    samples.append(0)
for i in range(tone):
    t = i / sr
    # Fade in first 100ms, fade out last 100ms
    env = min(1.0, i / (sr * 0.1), (tone - i) / (sr * 0.1))
    samples.append(int(16000 * env * math.sin(2 * math.pi * 440 * t)))
with wave.open('$TONE_WAV', 'wb') as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(sr)
    wf.writeframes(struct.pack(f'<{len(samples)}h', *samples))
print(f'Tone generated: {len(samples)} samples, {len(samples)/sr:.1f}s')
" 2>&1
    info "$(python3 -c "print(f'Tone: 440Hz, 2s with 500ms DAC wake silence')")"

    # Play the tone
    info "Playing 440Hz tone on HDMI (plughw:0,3)..."
    info ">>> You should hear a tone from the HDMI display <<<"
    if paplay "$TONE_WAV" 2>/dev/null; then
        pass "paplay completed without error"
    else
        fail "paplay failed"
        info "Starting PulseAudio for HDMI pin-ctl..."
        pulseaudio --start --exit-idle-time=-1 2>/dev/null || true
        sleep 2
        info "Retrying paplay..."
        if paplay "$TONE_WAV" 2>/dev/null; then
            pass "paplay works after starting PulseAudio"
        else
            fail "paplay still fails — check HDMI connection and PA config"
        fi
    fi

    # Play TTS sample if available
    TTS_WAV="$TMP/tts_test.wav"
    if [ -f "$TTS_WAV" ]; then
        info "Playing TTS sample on HDMI..."
        info ">>> You should hear: 'Systems nominal. Boost pressure...' <<<"
        paplay "$TTS_WAV" 2>/dev/null || warn "TTS playback failed"
    fi
}

# ===================================================================
# Test 5: Full voice pipeline (mic → STT → wake word → LLM → TTS → HDMI)
# ===================================================================
test_pipeline() {
    header "Test 5: Voice Pipeline (End-to-End)"
    detect_mic
    [ -z "$MIC_DEVICE" ] && return

    info "This test requires you to speak."
    info "When prompted, say: 'Hey KiSTI, what's your name?'"
    info ""
    info "Recording in 3 seconds..."
    sleep 3

    # Record 5 seconds of speech
    PIPE_WAV="$TMP/pipeline_test.wav"
    info ">>> SPEAK NOW: 'Hey KiSTI, what's your name?' <<<"
    arecord -D "$MIC_DEVICE" -f S16_LE -r 16000 -c 1 -d 5 "$PIPE_WAV" 2>/dev/null

    if [ ! -f "$PIPE_WAV" ] || [ ! -s "$PIPE_WAV" ]; then
        fail "No audio captured"
        return
    fi

    # Run through STT
    info "Transcribing..."
    PIPELINE_RESULT=$(python3 -c "
import sys, json
sys.path.insert(0, '$KISTI_DIR')
from voice.stt_engine import STTEngine
from voice.llm_engine import LLMEngine
from voice.tts_engine import TTSEngine

# STT
stt = STTEngine()
stt.start()
stt_result = stt.transcribe_file('$PIPE_WAV')
stt.stop()

text = stt_result.text.strip()
if not text:
    print(json.dumps({'step': 'stt', 'error': 'empty transcription'}))
    exit(0)

# Check wake word
lower = text.lower()
wake_words = ['hey kisti', 'hey ki', 'kisti']
has_wake = any(w in lower for w in wake_words)

# Strip wake word to get query
query = text
for w in wake_words:
    idx = lower.find(w)
    if idx >= 0:
        query = text[idx + len(w):].strip(' ,.')
        break

# LLM
llm = LLMEngine()
llm.start()
llm_result = llm.query(user_message=query or text, telemetry_context='No telemetry.', si_drive_mode='Intelligent')
llm.stop()

# TTS
tts = TTSEngine()
tts.start()
tts_result = tts.speak(llm_result.text)
tts.stop()

print(json.dumps({
    'step': 'complete',
    'stt_text': text,
    'stt_latency': stt_result.latency_s,
    'wake_word': has_wake,
    'query': query,
    'llm_text': llm_result.text,
    'llm_tier': llm_result.tier,
    'llm_latency': llm_result.latency_s,
    'tts_duration': tts_result.duration_s,
    'tts_latency': tts_result.latency_s,
    'tts_bytes': len(tts_result.audio_pcm),
}))
" 2>&1)

    # Parse result
    STEP=$(echo "$PIPELINE_RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('step','error'))" 2>/dev/null || echo "error")

    if [ "$STEP" = "error" ] || [ "$STEP" = "stt" ]; then
        fail "Pipeline failed at STT — empty transcription or error"
        info "Raw output: $PIPELINE_RESULT"
        return
    fi

    # Extract fields
    STT_TEXT=$(echo "$PIPELINE_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['stt_text'])" 2>/dev/null)
    WAKE=$(echo "$PIPELINE_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['wake_word'])" 2>/dev/null)
    LLM_TEXT=$(echo "$PIPELINE_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['llm_text'])" 2>/dev/null)
    LLM_TIER=$(echo "$PIPELINE_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['llm_tier'])" 2>/dev/null)
    TTS_DUR=$(echo "$PIPELINE_RESULT" | python3 -c "import sys,json; print(f\"{json.load(sys.stdin)['tts_duration']:.1f}\")" 2>/dev/null)
    TTS_BYTES=$(echo "$PIPELINE_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['tts_bytes'])" 2>/dev/null)

    info "STT: '$STT_TEXT'"
    if [ "$WAKE" = "True" ]; then
        pass "Wake word detected"
    else
        warn "Wake word NOT detected in: '$STT_TEXT'"
    fi

    info "LLM ($LLM_TIER): '$LLM_TEXT'"
    if [ -n "$LLM_TEXT" ] && [ "$LLM_TEXT" != "None" ]; then
        pass "LLM responded"
    else
        fail "LLM returned empty response"
    fi

    info "TTS: ${TTS_DUR}s, $TTS_BYTES bytes"
    if [ "$TTS_BYTES" -gt 100 ] 2>/dev/null; then
        pass "TTS generated audio"
    else
        fail "TTS generated no audio"
        return
    fi

    # Write TTS output to WAV and play on HDMI
    info "Playing LLM response on HDMI..."
    RESPONSE_WAV="$TMP/pipeline_response.wav"
    python3 -c "
import sys, json, wave
sys.path.insert(0, '$KISTI_DIR')
from voice.tts_engine import TTSEngine
tts = TTSEngine()
tts.start()
result = tts.speak('''$LLM_TEXT''')
tts.stop()
# Prepend 500ms silence for DAC wake
silence = b'\x00\x00' * int(result.sample_rate * 0.5)
pcm = silence + result.audio_pcm
with wave.open('$RESPONSE_WAV', 'wb') as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(result.sample_rate)
    wf.writeframes(pcm)
" 2>/dev/null

    if [ -f "$RESPONSE_WAV" ] && [ -s "$RESPONSE_WAV" ]; then
        info ">>> You should hear KiSTI's response <<<"
        paplay "$RESPONSE_WAV" 2>/dev/null && \
            pass "End-to-end: Mic → STT → LLM → TTS → HDMI speaker" || \
            fail "HDMI playback failed in pipeline test"
    else
        fail "Could not generate response WAV"
    fi
}

# ===================================================================
# Test 6: Ollama LLM health check
# ===================================================================
test_ollama() {
    header "Test 6: Ollama LLM"

    if ! curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
        fail "Ollama not responding on :11434"
        return
    fi
    pass "Ollama is running"

    # Check model
    MODELS=$(curl -sf http://localhost:11434/api/tags | python3 -c "
import sys, json
data = json.load(sys.stdin)
for m in data.get('models', []):
    print(m['name'])
" 2>/dev/null)
    if echo "$MODELS" | grep -q "llama3.2:3b"; then
        pass "llama3.2:3b model loaded"
    else
        warn "llama3.2:3b not found. Available: $MODELS"
    fi

    # Quick inference test
    info "Testing LLM inference..."
    START_S=$(date +%s)
    LLM_OUT=$(curl -sf --max-time 30 http://localhost:11434/api/chat \
        -d '{"model":"llama3.2:3b","messages":[{"role":"user","content":"Say OK"}],"stream":false,"options":{"num_predict":5}}' 2>/dev/null)
    END_S=$(date +%s)
    ELAPSED=$((END_S - START_S))

    if [ -n "$LLM_OUT" ]; then
        RESPONSE=$(echo "$LLM_OUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('message',{}).get('content','')[:60])" 2>/dev/null)
        pass "LLM responded in ${ELAPSED}s: '$RESPONSE'"
    else
        fail "LLM inference failed or timed out"
    fi
}

# ===================================================================
# Main
# ===================================================================
MODE="${1:---all}"

echo -e "${BOLD}KiSTI Voice Pipeline Validation${NC}"
echo "$(date)"
echo "Repo: $KISTI_DIR"
echo ""

case "$MODE" in
    --mic)      test_mic ;;
    --stt)      test_stt ;;
    --tts)      test_tts ;;
    --hdmi)     test_hdmi ;;
    --ollama)   test_ollama ;;
    --pipeline) test_pipeline ;;
    --all)
        test_mic
        test_ollama
        test_tts
        test_stt
        test_hdmi
        test_pipeline
        ;;
    *)
        echo "Usage: $0 [--all|--mic|--stt|--tts|--hdmi|--ollama|--pipeline]"
        exit 1
        ;;
esac

# Summary
header "Summary"
echo -e "  ${GREEN}PASS: $PASS${NC}  ${RED}FAIL: $FAIL${NC}  ${YELLOW}WARN: $WARN${NC}"

if [ $FAIL -gt 0 ]; then
    echo -e "\n${RED}${BOLD}Voice pipeline has failures — fix before tune session${NC}"
    exit 1
else
    echo -e "\n${GREEN}${BOLD}Voice pipeline ready${NC}"
    exit 0
fi
