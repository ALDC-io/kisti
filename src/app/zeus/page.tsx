"use client";

import Nav from "@/components/Nav";
import { useRef, useEffect, useState, useCallback } from "react";
import { useZeusChat } from "@/components/chat/useZeusChat";
import ZeusChatMessage from "@/components/chat/ZeusChatMessage";
import ZeusScanBar from "@/components/chat/ZeusScanBar";
import ZeusVoiceWave from "@/components/chat/ZeusVoiceWave";
import { STARTER_CHIPS } from "@/lib/zeusResponses";
import { useVoiceInput } from "@/lib/useVoiceInput";

const CAPABILITIES = [
  "Vehicle telemetry & diagnostics",
  "Track session analysis",
  "Build specs & component details",
  "Performance comparisons",
  "Voice input & spoken responses",
];

export default function ZeusPage() {
  const { messages, processing, send, unlock, clear } = useZeusChat();
  const [input, setInput] = useState("");
  const [speaking, setSpeaking] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleTranscript = useCallback(
    (text: string) => {
      if (text.trim() && !processing) {
        send(text.trim());
      }
    },
    [send, processing],
  );

  const { recording, toggle: toggleMic } = useVoiceInput(handleTranscript);

  const handleSpeaking = useCallback(
    (active: boolean) => {
      setSpeaking(active);
      if (!active) unlock();
    },
    [unlock],
  );

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
    send(input);
    setInput("");
  };

  return (
    <>
      <Nav />
      <main className="flex min-h-screen flex-col pt-14">
        <div className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-4 py-8 lg:flex-row">
          {/* Left — info panel */}
          <aside className="shrink-0 lg:w-72">
            <div className="rounded-xl border border-white/10 bg-white/5 p-6">
              <div className="flex items-center gap-3">
                <img
                  src="/assets/aldc_logo.svg"
                  alt="ALDC"
                  className="h-5"
                  draggable={false}
                />
                <h1 className="text-xl font-bold text-foreground">Zeus Chat</h1>
                <span className="relative flex h-2 w-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-75" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-green-500" />
                </span>
              </div>

              <p className="mt-4 text-sm text-foreground/60">
                Talk to KiSTI directly. Ask about performance, telemetry, track
                sessions, or the build. Voice input supported &mdash; click the
                mic or just type.
              </p>

              <div className="mt-6">
                <h2 className="text-xs font-semibold uppercase tracking-wider text-foreground/40">
                  Capabilities
                </h2>
                <ul className="mt-3 space-y-2">
                  {CAPABILITIES.map((cap) => (
                    <li
                      key={cap}
                      className="flex items-center gap-2 text-sm text-foreground/60"
                    >
                      <span className="text-kisti-accent">&#9656;</span>
                      {cap}
                    </li>
                  ))}
                </ul>
              </div>

              <div className="mt-6">
                <h2 className="text-xs font-semibold uppercase tracking-wider text-foreground/40">
                  Powered By
                </h2>
                <div className="mt-3 flex flex-wrap gap-2">
                  {["Zeus Memory", "OpenAI Whisper", "TTS", "Edge AI"].map(
                    (tag) => (
                      <span
                        key={tag}
                        className="rounded-full border border-kisti-accent/20 bg-kisti-accent/5 px-2.5 py-1 text-xs text-kisti-accent"
                      >
                        {tag}
                      </span>
                    ),
                  )}
                </div>
              </div>

              {messages.length > 0 && (
                <button
                  onClick={clear}
                  className="mt-6 w-full rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm text-foreground/50 transition-colors hover:bg-white/10 hover:text-foreground/70"
                >
                  Clear conversation
                </button>
              )}
            </div>
          </aside>

          {/* Right — full chat */}
          <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl border border-white/10 bg-[#0d0d20] shadow-2xl shadow-kisti-accent/10">
            {/* Header bar */}
            <div className="shrink-0 border-b border-white/10">
              <div className="flex items-center justify-between px-6 py-4">
                <div className="flex items-center gap-2">
                  <img
                    src="/assets/kisti_logo.png"
                    alt="KiSTI"
                    className="h-5"
                    draggable={false}
                  />
                  <span className="text-sm font-bold text-foreground">
                    KiSTI Co-Driver
                  </span>
                </div>
                <span className="text-xs text-foreground/30">
                  {messages.length > 0
                    ? `${messages.length} message${messages.length === 1 ? "" : "s"}`
                    : "Ready"}
                </span>
              </div>
              <ZeusVoiceWave active={speaking} />
              <ZeusScanBar active={processing && !speaking} />
            </div>

            {/* Messages area */}
            <div
              ref={scrollRef}
              className="flex-1 space-y-4 overflow-y-auto px-6 py-6"
            >
              {messages.length === 0 && !processing ? (
                <div className="flex h-full flex-col items-center justify-center gap-6">
                  <div className="text-center">
                    <p className="text-lg font-semibold text-foreground/70">
                      Ask KiSTI anything
                    </p>
                    <p className="mt-1 text-sm text-foreground/40">
                      Type a question or try one of these
                    </p>
                  </div>
                  <div className="flex flex-wrap justify-center gap-2">
                    {STARTER_CHIPS.map((chip) => (
                      <button
                        key={chip}
                        onClick={() => send(chip)}
                        className="rounded-full border border-kisti-accent/20 bg-kisti-accent/5 px-4 py-2 text-sm text-kisti-accent transition-colors hover:bg-kisti-accent/15"
                      >
                        {chip}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                messages.map((msg, idx) => (
                  <ZeusChatMessage
                    key={msg.id}
                    message={msg}
                    onSpeaking={
                      msg.role === "zeus" && idx === messages.length - 1
                        ? handleSpeaking
                        : undefined
                    }
                  />
                ))
              )}
              {processing && messages.length > 0 && (
                <div className="flex justify-start">
                  <div className="rounded-2xl rounded-bl-sm bg-white/5 px-4 py-3 font-mono text-sm text-foreground/40">
                    <span className="animate-pulse">Zeus is thinking...</span>
                  </div>
                </div>
              )}
            </div>

            {/* Input bar */}
            <form
              onSubmit={handleSubmit}
              className="flex items-center gap-3 border-t border-white/10 px-6 py-4"
            >
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask me anything..."
                disabled={processing}
                className="flex-1 rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-foreground placeholder-foreground/30 outline-none transition-colors focus:border-kisti-accent/40"
              />
              <button
                type="button"
                onClick={toggleMic}
                disabled={processing}
                className={`rounded-xl px-4 py-3 text-sm transition-colors ${
                  recording
                    ? "animate-pulse bg-red-600 text-white"
                    : "bg-white/5 text-foreground/60 hover:bg-white/10 hover:text-foreground disabled:opacity-40"
                }`}
                aria-label={recording ? "Stop recording" : "Voice input"}
              >
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 16 16"
                  fill="currentColor"
                >
                  <path d="M8 1a2 2 0 00-2 2v5a2 2 0 004 0V3a2 2 0 00-2-2z" />
                  <path d="M4.5 7a.5.5 0 00-1 0A4.5 4.5 0 007.5 11.45v1.55h-2a.5.5 0 000 1h5a.5.5 0 000-1h-2v-1.55A4.5 4.5 0 0012.5 7a.5.5 0 00-1 0 3.5 3.5 0 01-7 0z" />
                </svg>
              </button>
              <button
                type="submit"
                disabled={processing || !input.trim()}
                className="rounded-xl bg-kisti-accent px-4 py-3 text-sm font-medium text-white transition-colors hover:bg-kisti-glow disabled:opacity-40"
              >
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 16 16"
                  fill="currentColor"
                >
                  <path d="M2.5 2.5a.5.5 0 01.7-.2l10.5 5.5a.5.5 0 010 .4L3.2 13.7a.5.5 0 01-.7-.6L4.5 8 2.5 3.1a.5.5 0 010-.6z" />
                </svg>
              </button>
            </form>
          </div>
        </div>
      </main>
    </>
  );
}
