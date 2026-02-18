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

/** Currently playing audio element (for OpenAI TTS) */
let activeAudio: HTMLAudioElement | null = null;

/** Whether the OpenAI API route is available (cached after first check) */
let apiAvailable: boolean | null = null;

async function speakViaAPI(text: string): Promise<boolean> {
  try {
    const res = await fetch("/api/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) {
      apiAvailable = false;
      return false;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);

    if (activeAudio) {
      activeAudio.pause();
      activeAudio = null;
    }

    const audio = new Audio(url);
    activeAudio = audio;
    audio.volume = 0.85;
    audio.onended = () => {
      URL.revokeObjectURL(url);
      activeAudio = null;
    };
    await audio.play();
    apiAvailable = true;
    return true;
  } catch {
    apiAvailable = false;
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

function stopAll() {
  if (activeAudio) {
    activeAudio.pause();
    activeAudio = null;
  }
  if ("speechSynthesis" in window) {
    speechSynthesis.cancel();
  }
}

export function useTTS() {
  const lastSpoken = useRef("");

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
      if (text === lastSpoken.current) return;
      lastSpoken.current = text;

      // Try OpenAI API first, fall back to browser SpeechSynthesis
      if (apiAvailable === false) {
        speakViaBrowser(text);
        return;
      }

      speakViaAPI(text).then((ok) => {
        if (!ok) speakViaBrowser(text);
      });
    },
    [muted]
  );

  return { speak, muted, toggleMute };
}
