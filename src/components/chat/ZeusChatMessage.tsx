"use client";

import { useEffect, useState, useRef } from "react";
import type { ChatMessage } from "./useZeusChat";

const CHAR_DELAY = 25;

interface ZeusChatMessageProps {
  message: ChatMessage;
  onSpeaking?: (active: boolean) => void;
}

export default function ZeusChatMessage({ message, onSpeaking }: ZeusChatMessageProps) {
  const [displayed, setDisplayed] = useState(
    message.role === "user" ? message.text : ""
  );
  const [done, setDone] = useState(message.role === "user");
  const onSpeakingRef = useRef(onSpeaking);
  onSpeakingRef.current = onSpeaking;

  useEffect(() => {
    if (message.role === "user") return;

    onSpeakingRef.current?.(true);
    let i = 0;
    const id = setInterval(() => {
      i++;
      setDisplayed(message.text.slice(0, i));
      if (i >= message.text.length) {
        clearInterval(id);
        setDone(true);
        onSpeakingRef.current?.(false);
      }
    }, CHAR_DELAY);

    return () => {
      clearInterval(id);
    };
    // Only re-run when the message itself changes, not when callback ref changes
  }, [message.id, message.text, message.role]);

  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-sm border border-kisti-accent/30 bg-kisti-accent/15 px-3.5 py-2.5 text-sm text-foreground">
          {message.text}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] rounded-2xl rounded-bl-sm bg-white/5 px-3.5 py-2.5 font-mono text-sm text-cyan-100/90 shadow-sm shadow-cyan-500/5">
        {displayed}
        {!done && (
          <span className="animate-cursor-blink ml-0.5 inline-block h-4 w-[2px] translate-y-[2px] bg-kisti-accent" />
        )}
      </div>
    </div>
  );
}
