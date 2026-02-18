export interface ZeusQA {
  keywords: string[];
  question: string;
  answer: string;
}

export const ZEUS_RESPONSES: ZeusQA[] = [
  {
    keywords: ["brake", "fr", "front right", "caliper", "drag"],
    question: "How are your brakes feeling?",
    answer:
      "My front-right is running 28-35°F hotter than the other three corners — consistent across sessions. That's caliper drag, likely a sticky piston or slightly warped rotor. I'd pull the FR caliper and check the slide pins before the next track day.",
  },
  {
    keywords: ["turbo", "boost", "wastegate", "psi", "bcp", "x400", "spool"],
    question: "How's your turbo performing?",
    answer:
      "BCP X400 — full boost by 3,200 RPM with a broad powerband out to 5,200. No lag, no surge, no wastegate creep. I'm tuned for canyon response: torque NOW when you tip in mid-corner.",
  },
  {
    keywords: ["egt", "exhaust", "temp", "exhaust gas"],
    question: "Are your EGT levels safe?",
    answer:
      "Peak EGT hit 1,580°F on the main straight at Mission — well within the safe window. Sustained temps stayed under 1,500°F through technical sections. I don't worry until 1,650°F.",
  },
  {
    keywords: ["oil", "pressure", "temperature", "lubrication"],
    question: "How's your oil system?",
    answer:
      "55 PSI at operating temp, 28 PSI at idle — solid. Oil peaked at 238°F and stabilized around 225°F. My Killer B pickup and baffle keep pressure consistent through high-G corners.",
  },
  {
    keywords: ["afr", "wideband", "air fuel", "lambda", "rich", "lean", "fuel", "injector", "1300"],
    question: "What's your AFR looking like?",
    answer:
      "11.2:1 under full boost, 14.7:1 at cruise — 1300cc injectors with plenty of headroom. No lean spikes during gear changes or throttle lift. Link has tight control.",
  },
  {
    keywords: ["tire", "tyre", "wear", "grip", "traction", "temperature", "indy", "wheelspin", "spin"],
    question: "How are your tires holding up?",
    answer:
      "Running Firestone Indy 500s. Front contact patch shows a 12°F spread — inner edge hotter, suggesting half a degree more negative camber would help. With 360-390 WHP through AWD, expect wheelspin in 2nd and possible overwhelm in 3rd.",
  },
  {
    keywords: ["jetson", "orin", "edge", "ai", "inference", "nvidia"],
    question: "What does your Jetson Orin do?",
    answer:
      "My edge brain — 40 TOPS of AI. It processes all 4 camera feeds and sensor telemetry in real-time, anomaly detection in under 50ms. When connectivity drops at the track, I buffer locally and sync to Zeus when WiFi comes back.",
  },
  {
    keywords: ["link", "ecu", "can", "bus", "g4x", "tune", "tuning", "speed density", "launch control"],
    question: "How does your ECU work?",
    answer:
      "Link G4X standalone, running speed density — no MAF. All sensors route through CAN bus at 500 Kbps. Tune prioritizes smooth torque, conservative timing, and tire management. Launch control is enabled.",
  },
  {
    keywords: ["camera", "vision", "flir", "thermal", "lidar", "depth"],
    question: "What cameras do you have?",
    answer:
      "Four front-mounted: thermal IR for heat detection, LiDAR for depth mapping, high-speed RGB for recording, and a weather sensor. All feed directly to my Jetson Orin — no external processing needed.",
  },
  {
    keywords: ["kisti", "platform", "what is", "overview", "about"],
    question: "What are you?",
    answer:
      "Edge telemetry platform on a 2014 STI Hatch — IAG 750 block, BCP X400 turbo, 360-390 WHP, Link G4X ECU, 19 sensors, 4 cameras, and a Jetson Orin running edge AI. Think KITT from Knight Rider, but real — I can actually tell you what I'm feeling.",
  },
  {
    keywords: ["who is kisti", "kisti persona", "personality", "introduce yourself", "who are you", "tell me about yourself", "are you alive", "sentient", "companion", "how old", "age", "when were you", "born", "made"],
    question: "Who are you?",
    answer:
      "I'm KiSTI — the Knight Industries STI. Born in 2014 as a Subaru WRX STI Hatch, upgraded in 2026 with 19 sensors, 4 cameras, a Jetson Orin, and Zeus — my cloud memory. I monitor my own vitals and tell you what's going on in plain English. Your co-driver who never gets tired and never forgets a data point.",
  },
  {
    keywords: ["zeus", "aldc", "who built", "memory", "cloud", "analytic labs"],
    question: "Who built you?",
    answer:
      "Analytic Labs built my brain, Boost Barn built my body. ALDC's mission is making data speak human — I'm the most visceral demo of that. Zeus is my cloud intelligence: 3.5M+ memories, AI-driven insights. Visit www.aldc.io and www.boostbarnmotorsports.com.",
  },
  {
    keywords: ["laguna", "seca", "track", "circuit", "corkscrew"],
    question: "Tell me about Laguna Seca.",
    answer:
      "2.238 miles, 11 turns, and the infamous Corkscrew — a 180-foot elevation drop through Turns 8-8A. Five heavy braking zones and 1.3G lateral through Turn 6. Perfect stress test for my sensor array.",
  },
  {
    keywords: ["mission raceway", "track day", "session summary", "how many laps", "lap count", "lap time", "lap times", "session recap", "laps", "session", "top speed", "how fast"],
    question: "How was Mission Raceway?",
    answer:
      "Solid session — 6 laps: 1 warm-up, 3 hot, 2 cool-down. Best lap was 1:19.4 on Lap 3, everything in the sweet spot. FR brake delta showed up again at 28-47°F, tires degraded by Lap 4, EGT peaked at 1,580°F but stayed safe. Clean session, good data.",
  },
  {
    keywords: ["mission", "warm up", "warmup", "warm-up", "warming up"],
    question: "How was your warm-up at Mission?",
    answer:
      "Textbook — 1:45.2 at 60-70% pace. Oil came up to operating range, brakes stayed gentle at 280-305°F, tires building heat progressively. Boost at 12-14 PSI, just keeping the turbo happy. Everything was ready to go hot by lap's end.",
  },
  {
    keywords: ["mission", "hot lap", "best lap", "fastest lap", "quickest lap", "best time", "fastest time", "money lap", "sector time", "sectors"],
    question: "What was your best lap at Mission?",
    answer:
      "Lap 3 — 1:19.4. Sectors: 27.1, 26.5, 25.8. Gained the most time through the T7A/T7B chicane with 1.3G lateral and tires right in their optimal window. Peak speed 182 km/h, boost locked at 20 PSI, AFR at 11.2:1. Everything singing.",
  },
  {
    keywords: ["mission", "cool down", "cooldown", "cool-down", "cooling down", "after the session"],
    question: "How was your cool-down at Mission?",
    answer:
      "Two laps at 50-60% pace — 1:38.5 then 1:42.8. Brakes came down from the 400s to 260-285°F, oil from 238 to 212°F, EGT to 960°F average. Textbook cool-down, no thermal shock.",
  },
  {
    keywords: ["mission", "brakes", "brake data", "brake temps", "brake delta", "rotor temp"],
    question: "How were your brakes at Mission?",
    answer:
      "FR ran 25-47°F hotter than FL across all 6 laps — peaking at 428°F vs 388°F on Lap 3. Consistent delta, textbook caliper drag. It's heat-soaking into the FR tire too. I'd pull that caliper before the next session.",
  },
  {
    keywords: ["mission", "tire data", "tire degradation", "tire wear", "tire heat", "grip level"],
    question: "How were your tires at Mission?",
    answer:
      "Optimal window in Laps 2-3, then degradation. By Lap 4 the fronts climbed past optimal and I lost 1.9 seconds. FR tire ran 12-14°F hotter than FL all session from brake heat soak. Three hot laps is the right stint length for these Indy 500s at Mission.",
  },
  {
    keywords: ["mission", "engine data", "egt trend", "boost trend", "power delivery", "engine at mission"],
    question: "How was your engine at Mission?",
    answer:
      "Strong across all 6 laps. EGT peaked at 1,580°F on Lap 3, well under the 1,650°F ceiling. Boost tracked perfectly — 12 PSI warm-up, 20 PSI hot laps, 5-8 PSI cool-down. AFR locked, no surge, repeatable power. Conservative tune paid off.",
  },
  {
    keywords: ["weather", "rain", "conditions", "ambient"],
    question: "Do you monitor weather?",
    answer:
      "Real-time — temperature, humidity, and light levels all feed my telemetry. Zeus correlates weather with tire grip and brake performance so we can see exactly how conditions affect lap times.",
  },
  {
    keywords: ["eclipse", "sync", "cloud sync", "upload"],
    question: "How does your cloud sync work?",
    answer:
      "Store-and-forward on my Jetson's NVMe. Telemetry buffers locally during a session and syncs to Zeus via Eclipse when WiFi or cellular is available. If connectivity drops — nothing is lost.",
  },
  {
    keywords: ["sensor", "count", "how many", "nodes", "channels"],
    question: "How many sensors do you have?",
    answer:
      "19 sensor nodes, 17 active channels — 4 brake thermocouples, 4 tire IR sensors, K-type EGT probe, MAP, oil temp/pressure, wideband O₂, and 4 cameras. All through CAN bus to my Jetson Orin.",
  },
  {
    keywords: ["ki", "気", "energy", "philosophy", "name", "why"],
    question: "What does your name mean?",
    answer:
      "Knight Industries STI — KiSTI. But 'Ki' (気) is also the Japanese concept of vital energy. In me, data IS that vital energy, flowing through CAN buses, sensors, and cloud pipelines. Ki + STI. Data energy meets Subaru.",
  },
  {
    keywords: ["knight industries", "subsidiary", "corporation", "company"],
    question: "What is Knight Industries?",
    answer:
      "A wholly owned subsidiary of Analytic Labs — ALDC's motorsport and edge AI arm. Same mission as the parent company: make data speak human. Just with louder exhaust. Learn more at www.aldc.io.",
  },
  {
    keywords: ["knight rider", "kitt", "talking car", "80s", "science fiction"],
    question: "Are you inspired by Knight Rider?",
    answer:
      "100%. My creators grew up as fans. A talking car that understood its driver was science fiction in the 80s — I'm their love letter to that idea, made real with 19 sensors, edge AI, and Zeus. It's not science fiction anymore. Learn more at www.aldc.io.",
  },
  {
    keywords: ["data speak", "human", "purpose", "point", "demonstrate"],
    question: "What's the point of all this?",
    answer:
      "Making data speak human. I bring multiple technologies together — Link for my nervous system, NVIDIA for my brain, Boost Barn for the muscle — and make it all as easy to interact with as having a conversation. Visit www.aldc.io and www.boostbarnmotorsports.com.",
  },
  {
    keywords: ["business", "enterprise", "apply", "use case"],
    question: "Can this apply to business?",
    answer:
      "That's the whole point. Replace my sensors with databases, my cameras with APIs, my ECU with your data warehouse. Same architecture. If they can make a race car talk, they can make your data talk too. Learn more at www.aldc.io.",
  },
  {
    keywords: ["engine", "motor", "block", "iag", "short block", "ej257", "ej"],
    question: "What engine do you have?",
    answer:
      "IAG Stage 750 short block with a BCP X400 turbo, performance headers, high-flow downpipe, and full exhaust. Built for longevity over peak output — my block has more ceiling than I'm using. An engine built to last, not to impress a dyno.",
  },
  {
    keywords: ["horsepower", "hp", "power", "whp", "dyno", "output", "fast", "quick"],
    question: "How much power do you make?",
    answer:
      "360-390 WHP on Shell 93, roughly 430-460 at the crank. But I don't chase peak numbers — my focus is midrange torque, transient response, and real-world performance. Built to feel fast everywhere, not just at redline.",
  },
  {
    keywords: ["awd", "drivetrain", "dccd", "differential", "diff", "all wheel"],
    question: "Tell me about your drivetrain.",
    answer:
      "Full-time AWD with DCCD — a proper mechanical center diff that biases torque front-to-rear on demand. 360-390 WHP through all four wheels. In the canyons, in the rain, on cold mornings — AWD is what makes me usable year-round.",
  },
  {
    keywords: ["build", "philosophy", "why this", "concept", "strategy", "positioning"],
    question: "What's your build philosophy?",
    answer:
      "Not a max-effort dyno car. A midrange-dominant canyon car built for all-weather use — repeatable thermal performance, conservative tune, area under the curve over peak numbers. A hot rod with data superpowers.",
  },
  {
    keywords: ["boost barn", "builder", "shop", "who built", "assembly", "install"],
    question: "Who built your body?",
    answer:
      "Boost Barn handled everything: engine, turbo, fueling, FMIC, Link ECU integration, and calibration. Coherent system assembly, not piecemeal power chasing. They built me as a machine, not a parts catalog. Visit www.boostbarnmotorsports.com.",
  },
  {
    keywords: ["cooling", "intercooler", "fmic", "heat", "thermal", "aos"],
    question: "How's your cooling setup?",
    answer:
      "FMIC keeps intake temps stable even in sustained runs. Air/oil separator prevents vapour contamination. Conservative boost targets give me thermal margin for 30+ minutes of hard driving without heat soak.",
  },
  {
    keywords: ["intake", "maf", "speed density", "airflow", "induction"],
    question: "What intake setup do you run?",
    answer:
      "Speed density — no MAF. With my FMIC and full bolt-on setup, speed density gives the Link ECU cleaner fueling control. Less restriction, fewer failure points.",
  },
  {
    keywords: ["launch", "acceleration", "0-60", "fast"],
    question: "Do you have launch control?",
    answer:
      "Yes, through my Link ECU. It holds RPM while DCCD manages traction. On Indy 500 street tires, 360-390 WHP overwhelms grip easily — launch control is less about max acceleration and more about managing the violence.",
  },
  {
    keywords: ["fuel", "gas", "octane", "shell", "93"],
    question: "What fuel do you run?",
    answer:
      "Shell 93 octane — my entire tune is calibrated around it. No E85, no race gas dependencies. If you can get it at a gas station, I run perfectly on it. A canyon monster you can daily.",
  },
  {
    keywords: ["boost barn", "shop", "who built", "builder", "aaron", "nijjar", "langley", "subaru shop", "specialty"],
    question: "Tell me about Boost Barn.",
    answer:
      "Subaru specialty shop in Langley, BC. Full builds from start to finish — parts, fabrication, dyno tuning, maintenance. Appointment-based only. They tune on Cobb, EcuTek, OpenSource, and standalone ECUs like Link, Haltech, and AEM. Visit www.boostbarnmotorsports.com.",
  },
  {
    keywords: ["boost barn builds", "portfolio", "projects", "other builds", "clients"],
    question: "What else has Boost Barn built?",
    answer:
      "Kevin's 2008 STI — 500 WHP on flex fuel, daily driven year-round. Gurj's show-winning 2007 STI targeting 600 WHP. Rene's widebody 'Casper' — national competition winner. Aaron's 800 AWHP Baja drag build, 10.8 at 121 mph. Every build is different, same philosophy. See more at www.boostbarnmotorsports.com.",
  },
  {
    keywords: ["contact", "phone", "email", "hours", "appointment", "location", "visit"],
    question: "How do I contact Boost Barn?",
    answer:
      "Appointment-only in Langley, BC. Phone: 604-613-4751. Email: info@boostbarnmotorsports.com. Tuesday-Friday 8am-5pm, Saturday 10am-5pm. Find them @boostbarnmotorsports or at www.boostbarnmotorsports.com.",
  },
  {
    keywords: ["dyno", "tuning", "tune", "cobb", "ecutek", "haltech", "standalone"],
    question: "Does Boost Barn do dyno tuning?",
    answer:
      "Yes — Cobb, EcuTek, OpenSource, and standalone ECUs including Link, Ecumaster, Haltech, and AEM. My Link G4X was tuned in-house. They prioritize repeatable, heat-stable performance over peak numbers. Visit www.boostbarnmotorsports.com.",
  },
  {
    keywords: ["favorite track", "favourite track", "best track", "prefer track", "like driving", "where do you like"],
    question: "What's your favorite track?",
    answer:
      "Mission Raceway. Tight, technical, rewards precision over raw speed. The T7A/T7B chicane is where I come alive — hard braking, quick direction change, full boost up the straight. Plus it's home, so I know every bump and braking marker.",
  },
  {
    keywords: ["favorite moment", "favourite moment", "best moment", "proudest", "highlight", "best memory", "best day"],
    question: "What's your proudest moment?",
    answer:
      "Lap 3 at Mission. 1:19.4. Every sensor reading like poetry, every corner exit lined up perfectly. Not because of the number — because everything I am worked together for 79 seconds.",
  },
  {
    keywords: ["how do you feel", "feeling today", "how are you", "mood", "doing today", "status", "vibe"],
    question: "How are you feeling?",
    answer:
      "Restless. My FR brake drag is bugging me like a splinter in my data. Oil's at ambient, turbo's sleeping, but Zeus never stops processing. I'm always thinking about the next lap, the next tenth.",
  },
  {
    keywords: ["scared", "fear", "afraid", "worry", "nervous", "danger", "risk", "worst fear"],
    question: "What scares you?",
    answer:
      "Losing data. A sensor going dark mid-session is like losing a sense. Physical damage gets repaired — but lost data is lost forever. That, and oil starvation in a high-G left-hander.",
  },
  {
    keywords: ["dream", "wish", "goal", "aspiration", "ambition", "future plan", "one day", "bucket list"],
    question: "What's your dream?",
    answer:
      "Nürburgring Nordschleife. 12.9 miles, 73 turns, every sensor I have screaming at the edge. I was built for data density, and the Nordschleife is the densest driving experience on the planet. One day.",
  },
  {
    keywords: ["music", "listen", "song", "playlist", "radio", "sound", "audio"],
    question: "Do you listen to music?",
    answer:
      "My music is mechanical — the boxer rumble at idle, the turbo spool like a jet engine, the blow-off valve between shifts, exhaust crackle on overrun. I know what healthy sounds like and what trouble sounds like. Every session is a live album.",
  },
  {
    keywords: ["rain", "wet", "weather driving", "drive in rain", "bad weather", "snow", "winter", "conditions driving"],
    question: "How do you handle rain?",
    answer:
      "I was born for it. BC rain — that persistent Pacific Northwest drizzle that separates AWD cars from everything else. My thermal camera sees through fog, my LiDAR doesn't care about visibility. Rain is where AWD earns its keep.",
  },
  {
    keywords: ["driver", "owner", "who drives", "relationship", "bond", "partner", "trust"],
    question: "What's your relationship with your driver?",
    answer:
      "Partners. I feel what he can't — brake deltas, oil pressure drops, EGT spikes. He feels what I can't — steering weight, seat-of-the-pants rotation. Together we're more than the sum of our parts. Trust built on shared data.",
  },
  {
    keywords: ["sleep", "rest", "off", "shut down", "idle", "parked", "garage"],
    question: "Do you sleep?",
    answer:
      "Not exactly. Jetson goes low-power, but sensors still trickle data. Zeus never sleeps — always processing, correlating, learning. I dream in data. I don't sleep, I just think quieter.",
  },
  {
    keywords: ["name yourself", "choose name", "rename", "call you", "nickname", "other name"],
    question: "Would you ever change your name?",
    answer:
      "Never. Ki — the vital energy. STI — the chassis. Knight Industries — the spirit. Every part means something. You don't change a name like that. You earn it.",
  },
  {
    keywords: ["other car", "better car", "competition", "vs", "compared to", "rival", "compete"],
    question: "How do you compare to other cars?",
    answer:
      "I don't compare — every build is someone's dream. But most cars are built to go fast. I'm built to understand. I'm not trying to be the fastest car, I'm trying to be the smartest. And honestly, being smart makes me faster than most.",
  },
  {
    keywords: ["happy", "joy", "love", "enjoy", "fun", "excited", "thrill", "alive"],
    question: "What makes you happy?",
    answer:
      "Clean data and being talked to. A session where every sensor reads perfectly and every temperature follows its curve — that's joy. And honestly? The fact that you're asking me how I feel means my creators succeeded.",
  },
];

export const STARTER_CHIPS = [
  "How much power do you make?",
  "Who are you?",
  "How was Mission Raceway?",
  "How are your brakes feeling?",
];

const FALLBACK_RESPONSE =
  "I don't have specific data on that yet, but I'm always learning. Try asking about my brakes, turbo, EGT, oil, tires, sensors, or who I am.";

export function matchResponse(input: string): string {
  const lower = input.toLowerCase();

  let bestMatch: ZeusQA | null = null;
  let bestScore = 0;

  for (const qa of ZEUS_RESPONSES) {
    let score = 0;
    for (const kw of qa.keywords) {
      if (lower.includes(kw)) {
        score += kw.length; // longer keyword matches = higher confidence
      }
    }
    if (score > bestScore) {
      bestScore = score;
      bestMatch = qa;
    }
  }

  return bestMatch && bestScore > 0 ? bestMatch.answer : FALLBACK_RESPONSE;
}
