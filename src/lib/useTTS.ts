"use client";

import { useCallback, useRef, useSyncExternalStore } from "react";

const MUTE_KEY = "kisti-tts-muted";
const SAMPLE_RATE = 24000;

const listeners = new Set<() => void>();
function getMuted(): boolean {
  if (typeof window === "undefined") return false;
  return localStorage.getItem(MUTE_KEY) === "true";
}
function subscribe(cb: () => void): () => void {
  listeners.add(cb);
  return () => listeners.delete(cb);
}
function notify() {
  listeners.forEach((cb) => cb());
}

let audioCtx: AudioContext | null = null;
let scheduledEnd = 0;
let abortController: AbortController | null = null;

function getAudioCtx(): AudioContext {
  if (!audioCtx) {
    audioCtx = new AudioContext({ sampleRate: SAMPLE_RATE });
  }
  return audioCtx;
}

function stopAll() {
  if (abortController) {
    abortController.abort();
    abortController = null;
  }
  if (audioCtx) {
    audioCtx.close().catch(() => {});
    audioCtx = null;
  }
  scheduledEnd = 0;
  speechQueue.length = 0;
  processing = false;
  if ("speechSynthesis" in window) {
    speechSynthesis.cancel();
  }
}

/**
 * Stream PCM from /api/tts and play chunks in real-time via Web Audio API.
 * PCM format: 24kHz, 16-bit signed LE, mono.
 */
async function speakViaAPI(text: string): Promise<boolean> {
  try {
    abortController = new AbortController();

    const res = await fetch("/api/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
      signal: abortController.signal,
    });

    if (!res.ok || !res.body) return false;

    const ctx = getAudioCtx();
    if (ctx.state === "suspended") await ctx.resume();
    scheduledEnd = ctx.currentTime;

    const reader = res.body.getReader();
    let leftover = new Uint8Array(0);

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      // Combine leftover bytes from previous chunk with new data
      const combined = new Uint8Array(leftover.length + value.length);
      combined.set(leftover);
      combined.set(value, leftover.length);

      // PCM is 16-bit (2 bytes per sample) — ensure even byte count
      const usableBytes = combined.length - (combined.length % 2);
      leftover = combined.slice(usableBytes);

      if (usableBytes === 0) continue;

      const samples = usableBytes / 2;
      const buffer = ctx.createBuffer(1, samples, SAMPLE_RATE);
      const channel = buffer.getChannelData(0);
      const view = new DataView(combined.buffer, combined.byteOffset, usableBytes);

      for (let i = 0; i < samples; i++) {
        // 16-bit signed LE → float [-1, 1]
        channel[i] = view.getInt16(i * 2, true) / 32768;
      }

      const source = ctx.createBufferSource();
      source.buffer = buffer;
      source.connect(ctx.destination);

      const startTime = Math.max(ctx.currentTime, scheduledEnd);
      source.start(startTime);
      scheduledEnd = startTime + buffer.duration;
    }

    // Wait for all scheduled audio to finish playing
    const remaining = scheduledEnd - getAudioCtx().currentTime;
    if (remaining > 0) {
      await new Promise((r) => setTimeout(r, remaining * 1000));
    }

    return true;
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") return false;
    return false;
  }
}

function speakViaBrowser(text: string): Promise<void> {
  return new Promise((resolve) => {
    if (!("speechSynthesis" in window)) { resolve(); return; }
    speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(text);
    utter.rate = 1.05;
    utter.pitch = 0.9;
    utter.volume = 0.8;
    utter.onend = () => resolve();
    utter.onerror = () => resolve();
    speechSynthesis.speak(utter);
  });
}

// --- Speech queue: process items sequentially ---
const speechQueue: string[] = [];
let processing = false;

async function processQueue() {
  if (processing) return;
  processing = true;

  while (speechQueue.length > 0) {
    if (getMuted()) {
      speechQueue.length = 0;
      break;
    }
    const text = speechQueue.shift()!;
    const ok = await speakViaAPI(text);
    if (!ok) await speakViaBrowser(text);
  }

  processing = false;
}

export function useTTS() {
  const speakingRef = useRef(false);

  const muted = useSyncExternalStore(subscribe, getMuted, () => false);

  const toggleMute = useCallback(() => {
    const next = !getMuted();
    localStorage.setItem(MUTE_KEY, String(next));
    if (next) stopAll();
    notify();
  }, []);

  const speak = useCallback(
    (text: string) => {
      if (muted) return;
      if (typeof window === "undefined") return;
      if (!text || text.length < 5) return;

      // Chat responses interrupt the queue and speak immediately
      if (speakingRef.current) stopAll();
      speakingRef.current = true;

      speakViaAPI(text).then((ok) => {
        if (!ok) speakViaBrowser(text);
        speakingRef.current = false;
      });
    },
    [muted]
  );

  /** Queue text to be spoken sequentially — does not interrupt current speech */
  const enqueue = useCallback(
    (text: string) => {
      if (muted) return;
      if (typeof window === "undefined") return;
      if (!text || text.length < 5) return;

      speechQueue.push(text);
      processQueue();
    },
    [muted]
  );

  return { speak, enqueue, muted, toggleMute };
}
