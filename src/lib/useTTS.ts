"use client";

import { useCallback, useRef, useSyncExternalStore } from "react";

/** localStorage key for TTS mute preference */
const MUTE_KEY = "kisti-tts-muted";

/** Simple external store for mute state so all consumers stay in sync */
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

/** Currently playing audio element */
let activeAudio: HTMLAudioElement | null = null;

function stopAll() {
  if (activeAudio) {
    activeAudio.pause();
    activeAudio = null;
  }
  if ("speechSynthesis" in window) {
    speechSynthesis.cancel();
  }
}

async function speakViaAPI(text: string): Promise<boolean> {
  try {
    const res = await fetch("/api/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) return false;

    const blob = await res.blob();
    if (blob.size < 100) return false;

    const url = URL.createObjectURL(blob);

    if (activeAudio) {
      activeAudio.pause();
      activeAudio = null;
    }

    return new Promise((resolve) => {
      const audio = new Audio(url);
      activeAudio = audio;
      audio.volume = 0.85;
      audio.onended = () => {
        URL.revokeObjectURL(url);
        activeAudio = null;
      };
      audio.onerror = () => {
        URL.revokeObjectURL(url);
        activeAudio = null;
        resolve(false);
      };
      audio.play().then(() => resolve(true)).catch(() => resolve(false));
    });
  } catch {
    return false;
  }
}

function speakViaBrowser(text: string) {
  if (!("speechSynthesis" in window)) return;
  speechSynthesis.cancel();
  const utter = new SpeechSynthesisUtterance(text);
  utter.rate = 1.05;
  utter.pitch = 0.9;
  utter.volume = 0.8;
  speechSynthesis.speak(utter);
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
      if (speakingRef.current) {
        stopAll();
      }

      speakingRef.current = true;

      // Always try API first, fall back to browser
      speakViaAPI(text).then((ok) => {
        if (!ok) speakViaBrowser(text);
        speakingRef.current = false;
      });
    },
    [muted]
  );

  return { speak, muted, toggleMute };
}
