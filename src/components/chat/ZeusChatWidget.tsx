"use client";

import { useState, useEffect, useCallback } from "react";
import { usePathname } from "next/navigation";
import { useZeusChat } from "./useZeusChat";
import ZeusChatPanel from "./ZeusChatPanel";

export default function ZeusChatWidget() {
  const pathname = usePathname();
  const [open, setOpen] = useState(pathname === "/");
  const { messages, processing, send, clear } = useZeusChat();

  const handleClose = useCallback(() => setOpen(false), []);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && open) {
        setOpen(false);
      }
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open]);

  return (
    <div className="fixed bottom-4 right-4 z-50">
      {/* Panel */}
      {open && (
        <div className="mb-3">
          <ZeusChatPanel
            messages={messages}
            processing={processing}
            onSend={send}
            onClose={handleClose}
          />
        </div>
      )}

      {/* FAB */}
      <button
        onClick={() => setOpen(!open)}
        className="group relative flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br from-kisti-accent to-kisti-glow text-white shadow-lg shadow-kisti-accent/25 transition-transform hover:scale-105 active:scale-95"
        aria-label={open ? "Close Zeus chat" : "Open Zeus chat"}
      >
        {/* Pulse ring */}
        {!open && (
          <span className="absolute inset-0 animate-fab-pulse rounded-full border-2 border-kisti-accent/40" />
        )}
        {open ? (
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
        ) : (
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
          </svg>
        )}
      </button>
    </div>
  );
}
