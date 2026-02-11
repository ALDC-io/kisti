"use client";

import { useRef, useEffect, useState } from "react";
import type { ChatMessage } from "./useZeusChat";
import ZeusChatMessage from "./ZeusChatMessage";
import ZeusScanBar from "./ZeusScanBar";
import { STARTER_CHIPS } from "@/lib/zeusResponses";

interface ZeusChatPanelProps {
  messages: ChatMessage[];
  processing: boolean;
  onSend: (text: string) => void;
  onClose: () => void;
}

export default function ZeusChatPanel({
  messages,
  processing,
  onSend,
  onClose,
}: ZeusChatPanelProps) {
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, processing]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || processing) return;
    onSend(input);
    setInput("");
  };

  return (
    <div className="flex w-[min(384px,calc(100vw-2rem))] max-h-[min(28rem,calc(100vh-6rem))] flex-col overflow-hidden rounded-2xl border border-white/10 bg-[#0d0d20] shadow-2xl shadow-kisti-accent/10">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
        <div className="flex items-center gap-2">
          <img
            src="/assets/aldc_logo.svg"
            alt="ALDC"
            className="h-4"
            draggable={false}
          />
          <span className="text-sm font-bold text-foreground">Zeus</span>
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-green-500" />
          </span>
        </div>
        <button
          onClick={onClose}
          className="rounded-md p-1 text-foreground/40 transition-colors hover:bg-white/5 hover:text-foreground/70"
          aria-label="Close chat"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
            <path d="M4.293 4.293a1 1 0 011.414 0L8 6.586l2.293-2.293a1 1 0 111.414 1.414L9.414 8l2.293 2.293a1 1 0 01-1.414 1.414L8 9.414l-2.293 2.293a1 1 0 01-1.414-1.414L6.586 8 4.293 5.707a1 1 0 010-1.414z" />
          </svg>
        </button>
      </div>

      {/* Scan bar */}
      <ZeusScanBar active={processing} />

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {messages.length === 0 && !processing ? (
          <div className="space-y-3">
            <p className="text-center text-xs text-foreground/40">
              Ask Zeus about the car
            </p>
            <div className="flex flex-wrap justify-center gap-2">
              {STARTER_CHIPS.map((chip) => (
                <button
                  key={chip}
                  onClick={() => onSend(chip)}
                  className="rounded-full border border-kisti-accent/20 bg-kisti-accent/5 px-3 py-1.5 text-xs text-kisti-accent transition-colors hover:bg-kisti-accent/15"
                >
                  {chip}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg) => <ZeusChatMessage key={msg.id} message={msg} />)
        )}
        {processing && messages.length > 0 && (
          <div className="flex justify-start">
            <div className="rounded-2xl rounded-bl-sm bg-white/5 px-3.5 py-2.5 font-mono text-sm text-foreground/40">
              <span className="animate-pulse">Zeus is thinking...</span>
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <form
        onSubmit={handleSubmit}
        className="flex items-center gap-2 border-t border-white/10 px-4 py-3"
      >
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about the car..."
          disabled={processing}
          className="flex-1 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-foreground placeholder-foreground/30 outline-none transition-colors focus:border-kisti-accent/40"
        />
        <button
          type="submit"
          disabled={processing || !input.trim()}
          className="rounded-lg bg-kisti-accent px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-kisti-glow disabled:opacity-40"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
            <path d="M2.5 2.5a.5.5 0 01.7-.2l10.5 5.5a.5.5 0 010 .4L3.2 13.7a.5.5 0 01-.7-.6L4.5 8 2.5 3.1a.5.5 0 010-.6z" />
          </svg>
        </button>
      </form>
    </div>
  );
}
