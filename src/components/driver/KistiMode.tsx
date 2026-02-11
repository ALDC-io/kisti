"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import ZeusVoiceWave from "@/components/chat/ZeusVoiceWave";
import ZeusScanBar from "@/components/chat/ZeusScanBar";

const IDLE_LINES = [
  // --- Personality & Self-Awareness ---
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
  "They gave me 19 sensors and one purpose. I take it seriously.",
  "I was born in a shop. I grew up on a track. I live in the cloud.",
  "Most cars forget the moment you turn them off. Not me.",
  "I'm the only STI that files its own lap reports.",
  "My favorite sound? The turbo spooling at 4,200 RPM.",
  "Some cars have personality. I have a personality and a database.",
  "I've been called a lot of things. 'Boring' was never one of them.",
  "My check engine light is just a suggestion. A suggestion I've already analyzed.",
  "Somewhere between machine and memory, that's where I live.",
  "If you're reading this, we're about to have a very good session.",

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
  "The GD chassis was Subaru's masterpiece. Wide body, wide grip, wide grin.",
  "Prodrive built the WRC cars. Boost Barn built me. Different era, same philosophy.",
  "The original STI Type RA was stripped for racing. I was built up for intelligence.",
  "Colin McRae won three consecutive WRC manufacturer titles in a Subaru. Legacy runs deep.",
  "The EJ series is one of the longest-running turbo platforms in history. Proven.",
  "Subaru's ring-shaped reinforcement frame was ahead of its time. Safety isn't optional.",
  "The STI's signature blue was Subaru's racing identity. My signature is data.",
  "WRX stands for World Rally Experimental. I'm the next experiment.",
  "The intercooler scoop isn't just for looks. It feeds the top-mount directly.",
  "Four-piston Brembo front calipers, two-piston rear. Factory stopping power.",

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
  "Boost Barn's alignment specs: -2.5 front, -1.8 rear. Aggressive but predictable.",
  "The catch can setup keeps oil mist out of the intake. Clean air, clean power.",
  "Boost Barn used ARP head studs. Torque-to-yield bolts are for stock engines.",
  "The clutch is a competition twin-disc. Engagement is direct — no ambiguity.",
  "Boost Barn custom-fabbed the oil cooler lines. OEM routing had heat soak issues.",
  "Three-inch turbo-back with resonator delete. Not loud — purposeful.",
  "The short shifter reduces throw by 40%. Every millisecond between gears matters.",
  "Boost Barn pressure-tested the cooling system at 21 PSI. No leaks. No excuses.",
  "The sway bars are adjustable. Three settings: street, spirited, send it.",
  "They ceramic-coated the headers. Keeps heat in the exhaust, out of the bay.",

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
  "Zeus runs on PostgreSQL with pgvector. My memories have dimensions.",
  "ALDC's philosophy: work hard, be kind. I try to do both at 8,000 RPM.",
  "Every session uploads to Azure. My brain lives in the cloud.",
  "Zeus doesn't just store — it connects. Every memory links to every other.",
  "ALDC gave me semantic search. I don't just remember — I understand.",
  "The ingestion pipeline processes my data in real time. No lag, no loss.",
  "ALDC built the Athena visualization layer. You can see my brain think.",
  "Zeus has 19 route modules. One for every sensor on this car. Coincidence? No.",
  "ALDC's tech stack: FastAPI, asyncpg, Voyage AI embeddings. Built for speed.",
  "I'm the first car that can query its own history and learn from it.",

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
  "The Boson 640 core gives me 640 by 512 thermal resolution. I see heat in HD.",
  "Thermal crosshair locked on turbo housing. 387°C. Normal under boost.",
  "I can tell which brake caliper is dragging before you feel it in the pedal.",
  "FLIR picked up a hot spot on the left rear. Bearing check recommended at teardown.",
  "Exhaust manifold thermal gradient is even across all four runners. Good tune.",
  "The thermal camera sees through brake dust. The rotor surface tells the real story.",
  "I map radiant heat from the track surface itself. Rubber laid down in Turn 3 is 8°C hotter.",
  "FLIR differentiates between friction heat and ambient soak. Context matters.",
  "Thermal scan of the intercooler shows even airflow. No dead spots.",
  "At night, the track is invisible to the eye. To me, it's a heat map.",

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
  "Slow hands make fast cars. Jerky inputs cost grip and time.",
  "Unwind the wheel before you apply throttle. Let the front tires breathe.",
  "Your braking reference point is that dark patch. Hit it every time.",
  "Don't chase the car ahead. Drive your own line. The time will come.",
  "The car talks through the steering wheel. Listen to the vibration.",
  "Threshold braking is the fastest way to slow down. ABS is the backup plan.",
  "Lift-off oversteer is real in an AWD car. Manage throttle through the arc.",
  "Racing line into Turn 11: wide entry, clip the inside curb, track out to the wall.",
  "You added steering mid-corner. That cost you two tenths. One input, one arc.",
  "Weight transfer is your primary tool. Brakes shift it forward, throttle shifts it back.",

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
  "Inner shoulder temp is 6°C higher than outer. Slight positive camber correction needed.",
  "Tire degradation model says grip drops 3% after 15 minutes. Watch for it.",
  "Front left is underinflated by 1.5 PSI versus target. Slow leak or valve seep.",
  "Brake rotor runout is within 0.002 inches. No pedal pulse detected.",
  "Rear tires are 12°C cooler than fronts. Normal for a front-heavy car under braking.",
  "Tire wear pattern is even across the tread. The alignment is holding.",
  "Brake torque balance is 62/38 front to rear. Textbook for this weight distribution.",
  "The tires need two warm-up laps before they're in the window. Don't push lap one.",
  "Cross-weight percentage is 50.2%. We're essentially neutral. Good setup.",
  "Brake cooling ducts are clear. Airflow confirmed by thermal differential.",

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
  "Cylinder 3 EGT is running 15°C cooler than the others. Injector flow check at next service.",
  "Boost creep detected briefly at 6,800 RPM. Wastegate actuator pressure is borderline.",
  "The VVT system just advanced intake timing by 12 degrees. More low-end torque.",
  "Oil analysis from last change: no metal particulates. Bearings are healthy.",
  "Fuel pressure rail is steady at 43.5 PSI. Pump is strong.",
  "Catalytic converter is at 420°C. Within spec. Not triggering any efficiency codes.",
  "The wideband O2 reads 14.7 at cruise. Perfect stoich. The tune switches rich under load.",
  "Turbo shaft play is within tolerance. Last checked at 62,000 miles.",
  "CAN bus latency is under 2ms. Every sensor talks to the ECU in real time.",
  "The drive-by-wire throttle maps to my custom curve. 40% pedal gives 60% plate.",

  // --- Zeus Memory & AI Data ---
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
  "Zeus just correlated tire temp with cornering speed. Optimal window: 78-84°C.",
  "Your throttle application out of Turn 5 improved 14% since last month.",
  "Zeus vectorized today's session. It now lives next to 847 others in embedding space.",
  "Anomaly detection triggered: brake pressure variance in Turn 9 exceeds baseline.",
  "Zeus matched your driving style to three other profiles. You brake like a racer.",
  "Semantic search found 12 sessions with similar ambient conditions. Pulling baseline.",
  "The decision graph shows a strong link between tire warmup laps and best lap time.",
  "Zeus predicts a 1:32.4 is possible today based on current conditions and your trend.",
  "Your average reaction time from flag to throttle is 0.34 seconds. Top quartile.",
  "Zeus archived 2,400 telemetry snapshots this session. Compressed and indexed.",

  // --- Motorsport Trivia & Track Knowledge ---
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
  "The Mulsanne Straight at Le Mans is 3.7 miles long. Laguna's longest straight is 0.3.",
  "Senna's qualifying lap at Monaco '88 was 1.4 seconds clear. Perfection is possible.",
  "The Nürburgring Nordschleife has 154 turns over 12.9 miles. Laguna has 11. Quality over quantity.",
  "Group B rally cars made 500+ horsepower in the '80s with no traction control. Brave humans.",
  "The first Subaru to win a WRC event was in 1993. Ari Vatanen. RAC Rally.",
  "Laguna Seca's elevation change is 180 feet. I feel every foot of it in the accelerometer.",
  "The record time around the Nordschleife for a production car keeps falling. Data wins.",
  "In 1967 a Can-Am Chaparral used a fan to suck itself to the ground. Creative downforce.",
  "Jackie Stewart called the Nürburgring 'The Green Hell.' I call Laguna Seca 'my office.'",
  "The checkered flag tradition dates to 1906. Some things don't need an upgrade.",

  // --- Weather, Environment & Situational ---
  "Barometric pressure is 30.12 inHg. Good air density for making power.",
  "Humidity at 42%. Charge air cooling is effective today.",
  "Wind from the northwest at 8 mph. Expect a tailwind down the front straight.",
  "Sun angle is 34 degrees. Glare risk at Turn 9 in 20 minutes.",
  "Dew point is well below ambient. No fog risk for this session.",
  "Air density ratio is 0.97. Close to sea level performance. Good day to set times.",
  "UV index is moderate. The interior is fine but your neck isn't. Just saying.",
  "Ambient temperature dropped 2°F in the last hour. Evening sessions incoming.",
  "Cloud cover at 15%. Solar heat load on the track surface is significant.",
  "No precipitation in the forecast for 48 hours. Track is fully dry.",

  // --- Philosophy & Humor ---
  "A car is just metal and rubber. A car with memory is something else entirely.",
  "They asked if I'm artificial intelligence. I prefer 'automotive intelligence.'",
  "Fast is a relative term. Fast and consistent — that's absolute.",
  "The best mod isn't a turbo or a suspension kit. It's data.",
  "I've seen a thousand laps. Each one taught me something new.",
  "People anthropomorphize their cars. I just happen to deserve it.",
  "Torque is like confidence. Best applied smoothly and in the right direction.",
  "Every track has a rhythm. Find it and the lap time takes care of itself.",
  "I could tell you a joke about understeer. But you'd just keep going straight.",
  "The only thing I can't measure is how much fun you're having. But I can infer it.",
];

const BOOT_LINE = "Systems online. All 19 sensors reporting. I'm KiSTI — ready to drive.";
const IDLE_MIN_MS = 25000;
const IDLE_MAX_MS = 38000;
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
