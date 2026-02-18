"use client";

import { useState, useCallback, useRef } from "react";
import { matchResponse } from "@/lib/zeusResponses";
import { useTTS } from "@/lib/useTTS";

export interface ChatMessage {
  id: string;
  role: "user" | "zeus";
  text: string;
}

export function useZeusChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [processing, setProcessing] = useState(false);
  const lockedRef = useRef(false);
  const { speak } = useTTS();

  const send = useCallback((text: string) => {
    if (lockedRef.current || !text.trim()) return;

    lockedRef.current = true;
    setProcessing(true);

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      text: text.trim(),
    };

    setMessages((prev) => [...prev, userMsg]);

    const answer = matchResponse(text);
    const delay = 800 + Math.random() * 700;

    setTimeout(() => {
      const zeusMsg: ChatMessage = {
        id: `z-${Date.now()}`,
        role: "zeus",
        text: answer,
      };
      setMessages((prev) => [...prev, zeusMsg]);
      speak(answer);
      // Keep lockedRef true — unlock() is called when typewriter finishes
      // Safety: auto-unlock after max typewriter time + buffer
      const maxTypewriterMs = answer.length * 25 + 2000;
      setTimeout(() => {
        if (lockedRef.current) {
          lockedRef.current = false;
          setProcessing(false);
        }
      }, maxTypewriterMs);
    }, delay);
  }, []);

  const unlock = useCallback(() => {
    lockedRef.current = false;
    setProcessing(false);
  }, []);

  const clear = useCallback(() => {
    setMessages([]);
    lockedRef.current = false;
    setProcessing(false);
  }, []);

  return { messages, processing, send, unlock, clear };
}
