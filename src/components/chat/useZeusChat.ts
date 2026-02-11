"use client";

import { useState, useCallback } from "react";
import { matchResponse } from "@/lib/zeusResponses";

export interface ChatMessage {
  id: string;
  role: "user" | "zeus";
  text: string;
}

export function useZeusChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [processing, setProcessing] = useState(false);

  const send = useCallback(
    (text: string) => {
      if (processing || !text.trim()) return;

      const userMsg: ChatMessage = {
        id: `u-${Date.now()}`,
        role: "user",
        text: text.trim(),
      };

      setMessages((prev) => [...prev, userMsg]);
      setProcessing(true);

      const answer = matchResponse(text);
      const delay = 800 + Math.random() * 700; // 800-1500ms

      setTimeout(() => {
        const zeusMsg: ChatMessage = {
          id: `z-${Date.now()}`,
          role: "zeus",
          text: answer,
        };
        setMessages((prev) => [...prev, zeusMsg]);
        setProcessing(false);
      }, delay);
    },
    [processing]
  );

  const clear = useCallback(() => {
    setMessages([]);
    setProcessing(false);
  }, []);

  return { messages, processing, send, clear };
}
