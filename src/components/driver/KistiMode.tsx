"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import ZeusVoiceWave from "@/components/chat/ZeusVoiceWave";
import ZeusScanBar from "@/components/chat/ZeusScanBar";

const IDLE_LINES = [
  // Personality
  "Systems online. All 19 sensors reporting. I'm KiSTI — ready to drive.",
  "Running self-diagnostics... everything checks out. Let's roll.",
  "I don't sleep. I just wait for you to turn the key.",
  "You know what I love about track days? Every lap is a new dataset.",

  // STI facts
  "The STI's EJ257 made 310 horsepower stock. We're well past that now.",
  "Symmetrical AWD means I put power where it counts — all four corners.",
  "Boost Barn built me to handle 22 PSI all day. Currently at 18 — nice and conservative.",
  "Intercooler temps looking good. That top-mount is doing its job.",

  // Sensors & telemetry
  "Oil pressure holding steady at 55 PSI. That's where I like it.",
  "Front right brake is running a little warm. Keep an eye on Turn 5.",
  "All four cameras online. LiDAR, IR, RGB, and weather — I can see everything.",
  "Tire temps are balanced across all four corners. Alignment is dialed.",
  "Exhaust gas temps nominal. The tune is clean.",
  "Coolant steady at 185°F. The radiator upgrade was worth it.",

  // Boost Barn
  "Boost Barn didn't just build a car. They built a rolling laboratory.",
  "Every bolt on this car was torqued to spec. That's the Boost Barn way.",
  "The roll cage adds 47 pounds but saves everything that matters.",

  // ALDC & Zeus
  "Zeus synced 47 memories this session. Every lap tells a story.",
  "My memory architecture runs on Zeus. Nothing gets forgotten.",
  "ALDC's Zeus platform lets me learn from every session. I get better every time.",
  "Cloud sync active. Zeus is watching. Zeus remembers.",

  // Driving tips
  "Smooth inputs, smooth outputs. The car responds to what you give it.",
  "Trail braking into Turn 2 gains you three tenths. Trust the data.",
  "Late apex at the Corkscrew. Commit to the line and the car will follow.",
  "Traction control is off. You're in charge. Don't let me down.",

  // General
  "Weather station reads clear skies. Perfect conditions for fast laps.",
  "GPS lock acquired. Circuit mapping active.",
  "I've been tracking your braking points. You're getting more consistent.",
  "Data logging at 100Hz across all channels. Nothing escapes the record.",
  "The Kenwood's only 800 by 480, but I make every pixel count.",
  "Link ECU and I speak CAN at 500 kilobits. Fluent in torque.",
];

const BOOT_LINE = "Systems online. All 19 sensors reporting. I'm KiSTI — ready to drive.";
const IDLE_MIN_MS = 25000;
const IDLE_MAX_MS = 35000;
const TYPE_SPEED_MS = 35;

export default function KistiMode() {
  const [displayText, setDisplayText] = useState("");
  const [isSpeaking, setIsSpeaking] = useState(false);
  const usedLinesRef = useRef<Set<number>>(new Set());
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const typeTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mountedRef = useRef(true);
  const bootedRef = useRef(false);

  const typewriterLine = useCallback((line: string) => {
    if (!mountedRef.current) return;
    let charIdx = 0;
    setDisplayText("");
    setIsSpeaking(true);

    typeTimerRef.current = setInterval(() => {
      if (!mountedRef.current) return;
      charIdx++;
      setDisplayText(line.slice(0, charIdx));
      if (charIdx >= line.length) {
        if (typeTimerRef.current) clearInterval(typeTimerRef.current);
        typeTimerRef.current = null;
        setIsSpeaking(false);
      }
    }, TYPE_SPEED_MS);
  }, []);

  const pickNextLine = useCallback((): string => {
    // Filter out the boot line from idle rotation
    const available: number[] = [];
    for (let i = 0; i < IDLE_LINES.length; i++) {
      if (IDLE_LINES[i] === BOOT_LINE) continue;
      if (!usedLinesRef.current.has(i)) available.push(i);
    }
    // Reset if exhausted
    if (available.length === 0) {
      usedLinesRef.current.clear();
      for (let i = 0; i < IDLE_LINES.length; i++) {
        if (IDLE_LINES[i] !== BOOT_LINE) available.push(i);
      }
    }
    const pick = available[Math.floor(Math.random() * available.length)];
    usedLinesRef.current.add(pick);
    return IDLE_LINES[pick];
  }, []);

  const scheduleNext = useCallback(() => {
    const delay = IDLE_MIN_MS + Math.random() * (IDLE_MAX_MS - IDLE_MIN_MS);
    timerRef.current = setTimeout(() => {
      if (!mountedRef.current) return;
      const line = pickNextLine();
      typewriterLine(line);
      scheduleNext();
    }, delay);
  }, [pickNextLine, typewriterLine]);

  useEffect(() => {
    mountedRef.current = true;

    // Boot sequence on first mount
    if (!bootedRef.current) {
      bootedRef.current = true;
      typewriterLine(BOOT_LINE);
    } else {
      const line = pickNextLine();
      typewriterLine(line);
    }

    scheduleNext();

    return () => {
      mountedRef.current = false;
      if (timerRef.current) clearTimeout(timerRef.current);
      if (typeTimerRef.current) clearInterval(typeTimerRef.current);
    };
  }, [typewriterLine, pickNextLine, scheduleNext]);

  return (
    <div
      className="flex h-full w-full flex-col items-center justify-center gap-4 px-6"
      style={{ backgroundColor: "#0A0A0A" }}
    >
      {/* KiSTI logo */}
      <img
        src="/assets/kisti_logo.png"
        alt="KiSTI"
        style={{ height: 48 }}
        draggable={false}
      />

      {/* KITT voice waveform */}
      <div className="w-full max-w-[280px]">
        <ZeusVoiceWave active={isSpeaking} />
      </div>

      {/* KITT scan bar — always active */}
      <div className="w-full max-w-[320px]">
        <ZeusScanBar active={true} />
      </div>

      {/* Typewriter dialogue */}
      <div
        className="min-h-[40px] w-full max-w-[400px] text-center text-xs leading-relaxed"
        style={{ color: "#C0C0C0" }}
      >
        {displayText}
        {isSpeaking && (
          <span className="animate-pulse" style={{ color: "#E60000" }}>
            ▌
          </span>
        )}
      </div>
    </div>
  );
}
