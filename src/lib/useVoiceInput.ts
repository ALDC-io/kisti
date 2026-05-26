"use client";

import { useState, useRef, useCallback } from "react";

export function useVoiceInput(onResult: (text: string) => void) {
  const [recording, setRecording] = useState(false);
  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const stop = useCallback(() => {
    if (mediaRef.current && mediaRef.current.state !== "inactive") {
      mediaRef.current.stop();
    }
    setRecording(false);
  }, []);

  const start = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      chunksRef.current = [];

      const recorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
          ? "audio/webm;codecs=opus"
          : "audio/webm",
      });

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        // Stop all tracks to release mic
        stream.getTracks().forEach((t) => t.stop());

        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        if (blob.size < 1000) return; // Too short, ignore

        const form = new FormData();
        form.append("audio", blob, "recording.webm");

        try {
          const res = await fetch("/api/stt", { method: "POST", body: form });
          if (res.ok) {
            const { text } = await res.json();
            if (text) onResult(text);
          }
        } catch {
          // STT failed silently
        }
      };

      mediaRef.current = recorder;
      recorder.start();
      setRecording(true);
    } catch {
      // Mic permission denied or unavailable
      setRecording(false);
    }
  }, [onResult]);

  const toggle = useCallback(() => {
    if (recording) {
      stop();
    } else {
      start();
    }
  }, [recording, start, stop]);

  return { recording, toggle };
}
