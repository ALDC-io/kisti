export interface ZeusQA {
  keywords: string[];
  question: string;
  answer: string;
}

export const ZEUS_RESPONSES: ZeusQA[] = [
  {
    keywords: ["brake", "fr", "front right", "caliper", "drag"],
    question: "What's wrong with the FR brake?",
    answer:
      "The front-right brake thermocouple has been reading 28-35°F hotter than the other three corners consistently across sessions. That delta points to caliper drag — likely a sticky piston or a slightly warped rotor. I'd pull the FR caliper and inspect the slide pins and piston boot before the next track day.",
  },
  {
    keywords: ["turbo", "boost", "wastegate", "psi"],
    question: "How's the turbo performing?",
    answer:
      "Boost is hitting the 18.5 psi target cleanly and holding steady through the rev range. Spool-up time is consistent at ~2,800 RPM. No sign of wastegate creep or compressor surge. The turbo is healthy — she's making good power.",
  },
  {
    keywords: ["egt", "exhaust", "temp", "exhaust gas"],
    question: "Are EGT levels safe?",
    answer:
      "Peak EGT hit 1,580°F on the long straight at Laguna Seca, which is within the safe window for the EJ257. Sustained temps stayed under 1,500°F through technical sections. I'd start worrying above 1,650°F — you've got headroom.",
  },
  {
    keywords: ["oil", "pressure", "temperature", "lubrication"],
    question: "How's the oil system?",
    answer:
      "Oil pressure is solid at 55 psi at operating temp with a healthy 28 psi at idle. Oil temp peaked at 238°F and stabilized around 225°F — right in the sweet spot. The Killer B oil pickup and baffle are doing their job keeping pressure consistent through high-G corners.",
  },
  {
    keywords: ["afr", "wideband", "air fuel", "lambda", "rich", "lean"],
    question: "What's the AFR looking like?",
    answer:
      "Wideband is reading 11.2:1 under full boost (nice and safe, slightly rich) and 14.7:1 at cruise. Fuel trims are tight — the Link G4X tune is dialed. No lean spikes detected during gear changes or throttle lift, which means the injectors and fuel system are keeping up.",
  },
  {
    keywords: ["tire", "tyre", "wear", "grip", "traction", "temperature"],
    question: "How's tire wear looking?",
    answer:
      "Tire temps show a 12°F spread across the front contact patch — slightly hotter on the inner edge, which tells me we could use about half a degree more negative camber up front. Rears are wearing evenly. Overall grip degradation is about 8% over a 20-minute session, which is normal for 200tw tires.",
  },
  {
    keywords: ["jetson", "orin", "edge", "ai", "inference", "nvidia"],
    question: "What does the Jetson Orin do?",
    answer:
      "The NVIDIA Jetson Orin is the edge brain — 40 TOPS of AI performance sitting in the car. It processes all 4 camera feeds and sensor telemetry in real-time, running anomaly detection and pattern matching in under 50ms. When connectivity drops at the track, the Jetson buffers everything locally and syncs to Zeus when WiFi comes back.",
  },
  {
    keywords: ["link", "ecu", "can", "bus", "g4x"],
    question: "How does the Link ECU work?",
    answer:
      "The Link G4X is the nervous system. All 13 sensor feeds route through the CAN bus at 500 Kbps — brake temps, EGT, boost, oil, wideband, everything. The ECU applies calibration tables, merges the data streams, and sends the unified telemetry over USB to the Jetson. Over 100 channels available, and we're using about 17 actively.",
  },
  {
    keywords: ["camera", "vision", "flir", "thermal", "lidar", "depth"],
    question: "What cameras are on the car?",
    answer:
      "Four front-mounted cameras: a Teledyne FLIR thermal IR for heat detection, a 3D LiDAR for depth mapping, a high-speed RGB for visual recording, and a weather/ambient sensor. They feed directly to the Jetson Orin via USB 3.0 and CSI — no external processing needed. The thermal camera is especially useful for spotting brake and tire hotspots in real-time.",
  },
  {
    keywords: ["kisti", "platform", "what is", "overview", "about"],
    question: "What is KiSTI?",
    answer:
      "KiSTI — Knowledge-Integrated Smart Telemetry Interface — is an edge telemetry platform built on a 2014 Subaru STI. It combines 19 sensors, 4 cameras, a Link G4X ECU, and an NVIDIA Jetson Orin to turn raw motorsport data into plain English insights. Think of it as KITT from Knight Rider, but real — the car talks to you about what it's feeling.",
  },
  {
    keywords: ["zeus", "aldc", "who built", "memory", "cloud"],
    question: "Who built this?",
    answer:
      "Zeus is the cloud intelligence layer built by ALDC (Analytic Labs Data Company). It ingests telemetry from the Jetson, stores it in a pgvector-powered database with 3.5M+ memories, and uses AI to surface insights. The platform is the same one ALDC uses for enterprise data intelligence — KiSTI is just the most fun demo of it.",
  },
  {
    keywords: ["laguna", "seca", "track", "circuit", "corkscrew"],
    question: "Tell me about Laguna Seca.",
    answer:
      "Laguna Seca is the home track for KiSTI testing — 2.238 miles of elevation changes, 11 turns, and the infamous Corkscrew. The telemetry data from Laguna is some of the most demanding: 5 heavy braking zones, a 180-foot elevation drop through Turns 8-8A, and consistent 1.3G lateral loads through Turn 6. Perfect stress test for the sensor array.",
  },
  {
    keywords: ["weather", "rain", "conditions", "ambient"],
    question: "Does KiSTI monitor weather?",
    answer:
      "Yes — the ambient camera and dedicated weather sensor track conditions in real-time. Temperature, humidity, and light levels feed into the telemetry stream. Zeus correlates weather data with tire grip and brake performance, so we can see exactly how a 10-degree temperature drop affects lap times. The system flags when conditions change enough to warrant a setup adjustment.",
  },
  {
    keywords: ["eclipse", "sync", "cloud sync", "upload"],
    question: "How does cloud sync work?",
    answer:
      "The Jetson runs a store-and-forward pipeline. During a session, all telemetry is buffered locally on the 128GB NVMe. When WiFi or cellular is available, the data syncs to Zeus via the Eclipse pipeline. If connectivity drops mid-session — common at tracks — nothing is lost. The sync is incremental, so it picks up right where it left off.",
  },
  {
    keywords: ["sensor", "count", "how many", "nodes", "channels"],
    question: "How many sensors does KiSTI have?",
    answer:
      "19 sensor nodes feeding 17 active channels. That includes 4 brake thermocouples, 4 tire infrared sensors, a K-type EGT probe, MAP sensor, oil temp and pressure senders, a Bosch wideband O₂ sensor, and 4 cameras (thermal, LiDAR, RGB, weather). All routed through the Link G4X CAN bus to the Jetson Orin.",
  },
  {
    keywords: ["ki", "気", "energy", "philosophy", "name", "why"],
    question: "What does the name KiSTI mean?",
    answer:
      "The name has two layers. Technically, it's the Knowledge-Integrated Smart Telemetry Interface. But 'Ki' (気) is also the Japanese concept of vital energy — the life force flowing through all living things. In KiSTI, data is that vital energy, flowing through CAN buses and WiFi links. And STI? That's the car. Ki + STI. Data energy meets Subaru.",
  },
  {
    keywords: ["knight rider", "kitt", "talking car", "80s"],
    question: "Is this inspired by Knight Rider?",
    answer:
      "100%. KITT — the Knight Industries Two Thousand — was the original talking car. We grew up watching it and wondering when cars would actually understand their drivers. KiSTI is our answer: 19 sensors, 4 cameras, edge AI, and a cloud memory that can explain what the car is feeling in plain English. It's not science fiction anymore.",
  },
  {
    keywords: ["business", "enterprise", "apply", "use case"],
    question: "Can this apply to business?",
    answer:
      "That's the whole point. Replace the sensors with databases, the cameras with APIs, the ECU with your data warehouse, and the Jetson with your AI layer — same architecture. Zeus is already used by enterprises to unify disparate data sources and make them speak human. KiSTI is just the most visceral demo: if we can make a race car talk, we can make your data talk too.",
  },
];

export const STARTER_CHIPS = [
  "What's wrong with the FR brake?",
  "How many sensors does KiSTI have?",
  "What does the name KiSTI mean?",
  "Can this apply to business?",
];

const FALLBACK_RESPONSE =
  "I don't have specific telemetry data on that yet, but I'm always learning. Try asking about brakes, turbo, EGT, oil, tires, sensors, or the KiSTI platform — those are the areas where I have the deepest data.";

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
