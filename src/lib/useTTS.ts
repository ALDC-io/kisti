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

export function useTTS() {
  const lastSpoken = useRef("");

  const muted = useSyncExternalStore(subscribe, getMuted, () => false);

  const toggleMute = useCallback(() => {
    const next = !getMuted();
    localStorage.setItem(MUTE_KEY, String(next));
    if (next) {
      speechSynthesis.cancel();
    }
    notify();
  }, []);

  const speak = useCallback(
    (text: string) => {
      if (muted) return;
      if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
      if (text === lastSpoken.current) return;
      lastSpoken.current = text;

      speechSynthesis.cancel();
      const utter = new SpeechSynthesisUtterance(text);
      utter.rate = 1.05;
      utter.pitch = 0.9;
      utter.volume = 0.8;
      speechSynthesis.speak(utter);
    },
    [muted]
  );

  return { speak, muted, toggleMute };
}
