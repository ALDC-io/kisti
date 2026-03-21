"use client";

import { useState, useCallback, useRef } from "react";

/**
 * Zeus Voice Playback Hook — TTS audio + amplitude envelope.
 *
 * Fetches TTS audio from a server endpoint, computes the amplitude
 * envelope client-side, and provides synced playback controls.
 *
 * Usage:
 *   const { speak, isPlaying, envelope } = useVoicePlayback({
 *     ttsEndpoint: "/api/tts",
 *   });
 *   await speak("Hello, I'm KiSTI.");
 *   <VoiceWaveform envelope={envelope} isPlaying={isPlaying} />
 */

interface UseVoicePlaybackOptions {
  /** TTS API endpoint that returns audio (WAV or MP3) */
  ttsEndpoint?: string;
  /** Frames per second for envelope computation */
  fps?: number;
  /** Speech rate multiplier (lower = faster, for urgency) */
  rate?: number;
}

interface VoicePlaybackResult {
  /** Speak text — generates audio, computes envelope, plays */
  speak: (text: string, urgency?: "normal" | "alert" | "critical") => Promise<void>;
  /** Whether audio is currently playing */
  isPlaying: boolean;
  /** Pre-computed amplitude envelope (0.0-1.0 per frame) */
  envelope: number[];
  /** Stop current playback */
  stop: () => void;
}

const URGENCY_RATES: Record<string, number> = {
  normal: 1.1,
  alert: 0.7,
  critical: 0.6,
};

/**
 * Expand abbreviations for natural TTS pronunciation.
 */
function expandAbbreviations(text: string): string {
  return text
    .replace(/(\d+\.?\d*)\s*M\b/g, "$1 million")
    .replace(/(\d+\.?\d*)\s*K\b/g, "$1 thousand")
    .replace(/(\d+\.?\d*)\s*B\b/g, "$1 billion")
    .replace(/\bPSI\b/g, "P S I")
    .replace(/\bRPM\b/g, "R P M")
    .replace(/\bGHz\b/g, "gigahertz")
    .replace(/\bHz\b/g, "hertz")
    .replace(/\bAFR\b/g, "A F R")
    .replace(/\bEGT\b/g, "E G T")
    .replace(/\bECU\b/g, "E C U")
    .replace(/\bAWD\b/g, "all wheel drive")
    .replace(/\bDCCD\b/g, "D C C D")
    .replace(/\bKa\b/g, "K A")
    .replace(/°F\b/g, " degrees fahrenheit")
    .replace(/°C\b/g, " degrees celsius")
    .replace(/°\b/g, " degrees");
}

/**
 * Compute RMS amplitude envelope from an AudioBuffer.
 */
function computeEnvelope(buffer: AudioBuffer, fps: number): number[] {
  const data = buffer.getChannelData(0);
  const samplesPerFrame = Math.floor(buffer.sampleRate / fps);
  const numFrames = Math.floor(data.length / samplesPerFrame);
  const envelope: number[] = [];
  let maxAmp = 1;

  for (let i = 0; i < numFrames; i++) {
    const start = i * samplesPerFrame;
    const end = Math.min(start + samplesPerFrame, data.length);
    let sum = 0;
    for (let j = start; j < end; j++) {
      sum += data[j] * data[j];
    }
    const rms = Math.sqrt(sum / (end - start));
    envelope.push(rms);
    if (rms > maxAmp) maxAmp = rms;
  }

  // Normalize to 0-1
  if (maxAmp > 0) {
    for (let i = 0; i < envelope.length; i++) {
      envelope[i] /= maxAmp;
    }
  }

  return envelope;
}

export function useVoicePlayback(
  options: UseVoicePlaybackOptions = {},
): VoicePlaybackResult {
  const { ttsEndpoint = "/api/tts", fps = 40 } = options;
  const [isPlaying, setIsPlaying] = useState(false);
  const [envelope, setEnvelope] = useState<number[]>([]);
  const sourceRef = useRef<AudioBufferSourceNode | null>(null);
  const ctxRef = useRef<AudioContext | null>(null);

  const stop = useCallback(() => {
    if (sourceRef.current) {
      try {
        sourceRef.current.stop();
      } catch {
        /* already stopped */
      }
      sourceRef.current = null;
    }
    setIsPlaying(false);
    setEnvelope([]);
  }, []);

  const speak = useCallback(
    async (text: string, urgency: "normal" | "alert" | "critical" = "normal") => {
      if (isPlaying) return;

      const expanded = expandAbbreviations(text);
      const rate = URGENCY_RATES[urgency] || 1.1;

      try {
        // Fetch TTS audio from server
        const res = await fetch(ttsEndpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: expanded, rate }),
        });

        if (!res.ok) {
          // Fallback: use browser Speech Synthesis
          const utterance = new SpeechSynthesisUtterance(expanded);
          utterance.rate = 1 / rate;
          speechSynthesis.speak(utterance);
          return;
        }

        const arrayBuffer = await res.arrayBuffer();

        // Decode audio
        if (!ctxRef.current) {
          ctxRef.current = new AudioContext();
        }
        const ctx = ctxRef.current;
        const audioBuffer = await ctx.decodeAudioData(arrayBuffer);

        // Pre-compute envelope BEFORE playback
        const env = computeEnvelope(audioBuffer, fps);
        setEnvelope(env);

        // Play audio
        const source = ctx.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(ctx.destination);
        sourceRef.current = source;

        setIsPlaying(true);
        source.start();

        source.onended = () => {
          setIsPlaying(false);
          setEnvelope([]);
          sourceRef.current = null;
        };
      } catch (err) {
        console.error("Voice playback error:", err);
        setIsPlaying(false);
        setEnvelope([]);
      }
    },
    [isPlaying, ttsEndpoint, fps],
  );

  return { speak, isPlaying, envelope, stop };
}
