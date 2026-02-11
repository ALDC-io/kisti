"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import ZeusVoiceWave from "@/components/chat/ZeusVoiceWave";
import ZeusScanBar from "@/components/chat/ZeusScanBar";

const IDLE_LINES = [
  // --- Personality ---
  "Running self-diagnostics... everything checks out. Let's roll.",
  "I don't sleep. I just wait for you to turn the key.",
  "You know what I love about track days? Every lap is a new dataset.",
  "If I had a heartbeat, it would sync to the tach.",
  "I'm not just a car. I'm a platform.",
  "I process more data per lap than most offices do in a week.",
  "Every sensor is a question. Every reading is an answer.",
  "Idle is just my way of stretching.",
  "I dream in telemetry streams.",
  "You drive. I remember. We both get faster.",

  // --- STI / Subaru Knowledge ---
  "The STI's EJ257 made 310 horsepower stock. We're well past that now.",
  "Symmetrical AWD means I put power where it counts — all four corners.",
  "The EJ platform's boxer layout keeps the center of gravity low. Physics matters.",
  "Subaru built the STI for WRC. I was built for the next generation.",
  "DCCD center diff adjusting torque split in real time. Equal opportunity grip.",
  "Forged internals. Closed-deck block. This engine was built to be pushed.",
  "The 6-speed feels notchy from the outside. From in here, it's a precision instrument.",
  "STI heritage goes back to '94. I carry the legacy forward.",
  "Unequal-length headers gave the old ones that rumble. I've got my own signature.",
  "Boxer engines cancel their own vibrations. Smooth power delivery by design.",

  // --- Boost Barn Build ---
  "Boost Barn didn't just build a car. They built a rolling laboratory.",
  "Every bolt on this car was torqued to spec. That's the Boost Barn way.",
  "The roll cage adds 47 pounds but saves everything that matters.",
  "Boost Barn spec'd the turbo for mid-range torque. Smart choice for circuit work.",
  "The exhaust is full 3-inch with a high-flow cat. Breathe in, breathe out.",
  "Boost Barn runs every build on the dyno before delivery. No guessing.",
  "This intercooler setup drops charge temps 40 degrees. That's free horsepower.",
  "Boost Barn hand-welded the downpipe. It fits like it grew there.",
  "They corner-balanced me with the driver's weight included. That's attention to detail.",
  "The fuel system was upgraded to handle E85 if we ever want it.",

  // --- Analytic Labs / ALDC ---
  "Zeus synced 47 memories this session. Every lap tells a story.",
  "My memory architecture runs on Zeus. Nothing gets forgotten.",
  "ALDC's Zeus platform lets me learn from every session. I get better every time.",
  "Cloud sync active. Zeus is watching. Zeus remembers.",
  "ALDC built me to be more than a car. I'm a decision engine.",
  "Zeus Memory stores every telemetry snapshot. Patterns emerge across sessions.",
  "ALDC doesn't just collect data. They make it think.",
  "Three point five million memories and counting. I know a lot of cars.",
  "The ALDC team built Zeus to connect everything. I'm proof it works.",
  "Knight Industries. A subsidiary of Analytic Labs. Purpose-built for this.",

  // --- Teledyne FLIR Thermal ---
  "All four cameras online. LiDAR, IR, RGB, and weather — I can see everything.",
  "FLIR thermal reads brake rotor surface temp through the wheel gap.",
  "IR camera detects cold spots on tires before you feel the grip drop.",
  "Thermal imaging shows engine bay heat soak patterns in real time.",
  "The FLIR sensor range is -40 to 330°C. Covers everything from cold start to brake fade.",
  "Night sessions are where thermal really shines. Every heat source glows.",
  "FLIR data overlays on the track map. Hot braking zones light up red.",
  "Ambient thermal scan nominal. No unusual heat sources on circuit.",
  "Thermal delta between left and right tires tells me about camber wear.",
  "FLIR refresh rate is 60Hz. Faster than your reaction time.",

  // --- Track Driving Tips ---
  "Smooth inputs, smooth outputs. The car responds to what you give it.",
  "Trail braking into Turn 2 gains you three tenths. Trust the data.",
  "Late apex at the Corkscrew. Commit to the line and the car will follow.",
  "Traction control is off. You're in charge. Don't let me down.",
  "Look where you want to go, not where you are. Eyes up.",
  "Brake in a straight line, then release as you turn in. Basic physics.",
  "If the rear steps out, don't lift. Counter-steer and let the AWD sort it.",
  "The fastest line isn't always the shortest. Use the whole track.",
  "Heel-toe into Turn 6. Rev-match keeps the rear planted.",
  "Consistency before speed. Fast laps come from repeatable technique.",

  // --- Tire & Brake Telemetry ---
  "Oil pressure holding steady at 55 PSI. That's where I like it.",
  "Front right brake is running a little warm. Keep an eye on Turn 5.",
  "Tire temps are balanced across all four corners. Alignment is dialed.",
  "Coolant steady at 185°F. The radiator upgrade was worth it.",
  "Brake pad thickness sensors show 60% remaining. Plenty of session left.",
  "Front tire pressures rose 2 PSI from cold. Normal heat cycling.",
  "Rear brake bias is 38%. Tuned for stability under hard braking.",
  "Tire compound is operating in its window. Grip is at peak.",
  "Pad deposits detected on front left rotor. A few hard stops will clean it.",
  "Brake fluid temp steady at 180°C. DOT4 racing spec holds to 300°C.",

  // --- Engine & Powertrain ---
  "Exhaust gas temps nominal. The tune is clean.",
  "Boost Barn built me to handle 22 PSI all day. Currently at 18 — nice and conservative.",
  "Intercooler temps looking good. That top-mount is doing its job.",
  "Knock sensor reading zero. Fuel quality confirmed.",
  "Wastegate duty cycle at 62%. Room to push if you want it.",
  "Transmission oil temp stable. The cooler loop is doing its job.",
  "AFR sitting at 11.2 under boost. Rich enough to be safe, lean enough to be fast.",
  "Turbo spool time is 2,800 RPM. Keep it above 3K for instant response.",
  "Oil temp trending nominal after 4 laps. Fully heat-soaked now.",
  "Alternator output steady at 14.2V. Electronics are fully powered.",

  // --- Zeus Memory Data ---
  "I've been tracking your braking points. You're getting more consistent.",
  "Data logging at 100Hz across all channels. Nothing escapes the record.",
  "Zeus flagged a 0.3 second improvement in sector two over last session.",
  "Memory graph shows your cornering speed improving lap over lap.",
  "Zeus cross-referenced weather data. Grip levels match the prediction.",
  "Session comparison loaded. You're 1.2 seconds faster than your first visit.",
  "Zeus identified an early apex pattern in Turn 8. Tighten entry angle.",
  "Telemetry stored. 847 data points per second, all indexed.",
  "Zeus Memory retains every session. Your progress curve is visible.",
  "Pattern match: your fastest laps share the same braking marker at Turn 11.",

  // --- Motorsport Trivia ---
  "Weather station reads clear skies. Perfect conditions for fast laps.",
  "GPS lock acquired. Circuit mapping active.",
  "The Kenwood's only 800 by 480, but I make every pixel count.",
  "Link ECU and I speak CAN at 500 kilobits. Fluent in torque.",
  "Laguna Seca opened in 1957. I've catalogued every documented lap time since.",
  "The Corkscrew drops 59 feet in elevation over 450 feet. Commitment corner.",
  "Andretti Hairpin was renamed in 2023. I still call it Turn 2.",
  "The track surface was repaved in 2022. Grip levels are excellent.",
  "Laguna Seca is 2.238 miles. Short enough to memorize, long enough to challenge.",
  "Track temp is 12 degrees above ambient. Asphalt stores heat like a battery.",
];

const BOOT_LINE = "Systems online. All 19 sensors reporting. I'm KiSTI — ready to drive.";
const IDLE_MIN_MS = 25000;
const IDLE_MAX_MS = 35000;
const TYPE_SPEED_MS = 30;
const MAX_VISIBLE_MESSAGES = 8;

interface LogMessage {
  id: number;
  text: string;
}

export default function KistiMode() {
  const [messages, setMessages] = useState<LogMessage[]>([]);
  const [currentText, setCurrentText] = useState("");
  const [isSpeaking, setIsSpeaking] = useState(false);
  const usedLinesRef = useRef<Set<number>>(new Set());
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const typeTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mountedRef = useRef(true);
  const bootedRef = useRef(false);
  const msgIdRef = useRef(0);

  const typewriterLine = useCallback((line: string) => {
    if (!mountedRef.current) return;
    let charIdx = 0;
    setCurrentText("");
    setIsSpeaking(true);

    typeTimerRef.current = setInterval(() => {
      if (!mountedRef.current) return;
      charIdx++;
      setCurrentText(line.slice(0, charIdx));
      if (charIdx >= line.length) {
        if (typeTimerRef.current) clearInterval(typeTimerRef.current);
        typeTimerRef.current = null;
        setIsSpeaking(false);
        // Push completed line into scrolling log
        const id = ++msgIdRef.current;
        setMessages((prev) => [{ id, text: line }, ...prev].slice(0, MAX_VISIBLE_MESSAGES));
        setCurrentText("");
      }
    }, TYPE_SPEED_MS);
  }, []);

  const pickNextLine = useCallback((): string => {
    const available: number[] = [];
    for (let i = 0; i < IDLE_LINES.length; i++) {
      if (IDLE_LINES[i] === BOOT_LINE) continue;
      if (!usedLinesRef.current.has(i)) available.push(i);
    }
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
      {/* KiSTI logo — cropped to content region */}
      <div
        style={{
          height: 48,
          width: 200,
          overflow: "hidden",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <img
          src="/assets/kisti_logo.png"
          alt="KiSTI"
          style={{
            height: 148,
            objectFit: "cover",
            objectPosition: "center 32.5%",
          }}
          draggable={false}
        />
      </div>

      {/* KITT voice waveform */}
      <div className="w-full max-w-[280px]">
        <ZeusVoiceWave active={isSpeaking} />
      </div>

      {/* KITT scan bar — always active */}
      <div className="w-full max-w-[320px]">
        <ZeusScanBar active={true} />
      </div>

      {/* Scrolling message log — newest at top */}
      <div
        className="flex w-full max-w-[400px] flex-col gap-1"
        style={{ minHeight: 120, maxHeight: 160 }}
      >
        {/* Currently typing line */}
        {currentText && (
          <div
            className="text-center text-xs leading-relaxed"
            style={{ color: "#C0C0C0" }}
          >
            {currentText}
            {isSpeaking && (
              <span className="animate-pulse" style={{ color: "#C80A33" }}>
                ▌
              </span>
            )}
          </div>
        )}

        {/* Completed messages — fade with age */}
        {messages.map((msg, idx) => (
          <div
            key={msg.id}
            className="text-center text-xs leading-relaxed transition-opacity duration-500"
            style={{
              color: "#C0C0C0",
              opacity: Math.max(0.15, 1 - idx * 0.15),
            }}
          >
            {msg.text}
          </div>
        ))}
      </div>
    </div>
  );
}
