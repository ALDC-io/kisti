"use client";

import { useState, useCallback, useRef } from "react";
import { matchResponse } from "@/lib/zeusResponses";

export interface ChatMessage {
  id: string;
  role: "user" | "zeus";
  text: string;
}

export function useZeusChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [processing, setProcessing] = useState(false);
  const processingRef = useRef(false);

  const send = useCallback((text: string) => {
    if (processingRef.current || !text.trim()) return;

    processingRef.current = true;
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
      processingRef.current = false;
      setProcessing(false);
    }, delay);
  }, []);

  const clear = useCallback(() => {
    setMessages([]);
    processingRef.current = false;
    setProcessing(false);
  }, []);

  return { messages, processing, send, clear };
}
