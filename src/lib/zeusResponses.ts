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
    keywords: ["turbo", "boost", "wastegate", "psi", "bcp", "x400", "spool"],
    question: "How's the turbo performing?",
    answer:
      "Running a BCP X400 turbo — selected specifically for fast spool and strong midrange torque. Full boost comes on in the low-to-mid 3,000 RPM range with a broad usable powerband from about 3,200 to 5,200 RPM. This isn't a big-turbo-lag setup. It's tuned for canyon response — you want torque NOW when you tip in mid-corner, and the X400 delivers that. No compressor surge, no wastegate creep.",
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
    keywords: ["afr", "wideband", "air fuel", "lambda", "rich", "lean", "fuel", "injector", "1300"],
    question: "What's the AFR looking like?",
    answer:
      "Running 1300cc injectors with an upgraded high-flow fuel pump, tuned for stable Shell 93 octane operation. Wideband reads 11.2:1 under full boost — nice and safe, slightly rich for reliability — and 14.7:1 at cruise. The Link ECU has tight control over fuel trims. No lean spikes during gear changes or throttle lift, which means the fueling system has plenty of headroom for the X400's demands.",
  },
  {
    keywords: ["tire", "tyre", "wear", "grip", "traction", "temperature", "indy", "wheelspin", "spin"],
    question: "How's tire wear looking?",
    answer:
      "Running Firestone Indy 500s. Tire temps show a 12°F spread across the front contact patch — slightly hotter on the inner edge, suggesting about half a degree more negative camber up front would help. With ~360-390 WHP going through AWD, expect wheelspin in 2nd under aggressive throttle and possible overwhelm in 3rd on imperfect surfaces. Launch control will induce controlled spin through 1st and 2nd depending on surface conditions. The DCCD AWD system helps manage it, but there's a lot of torque for a street tire.",
  },
  {
    keywords: ["jetson", "orin", "edge", "ai", "inference", "nvidia"],
    question: "What does the Jetson Orin do?",
    answer:
      "The NVIDIA Jetson Orin is the edge brain — 40 TOPS of AI performance sitting in the car. It processes all 4 camera feeds and sensor telemetry in real-time, running anomaly detection and pattern matching in under 50ms. When connectivity drops at the track, the Jetson buffers everything locally and syncs to Zeus when WiFi comes back.",
  },
  {
    keywords: ["link", "ecu", "can", "bus", "g4x", "tune", "tuning", "speed density", "launch control"],
    question: "How does the Link ECU work?",
    answer:
      "The Link G4X is a full standalone ECU — not a Cobb Accessport piggyback, a proper standalone. It runs speed density (no MAF), which gives cleaner control with the FMIC and full bolt-on setup. All sensor feeds route through the CAN bus at 500 Kbps. The tune prioritizes smooth torque ramp, conservative ignition timing, and tire management in 2nd and 3rd. Launch control is enabled. The tuning philosophy is 'one change at a time' with logging discipline — no chasing peak dyno numbers, just repeatable heat-stable performance.",
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
      "KiSTI is an edge telemetry platform built on a 2014 Subaru WRX STI Hatch — GR chassis, AWD with DCCD. Under the hood: an IAG Stage 750 short block, BCP X400 turbo, 1300cc injectors, FMIC, full bolt-ons, all managed by a Link G4X standalone ECU. It makes roughly 360-390 WHP on Shell 93, tuned for midrange response over peak numbers. On top of that sits 19 sensors, 4 cameras, and an NVIDIA Jetson Orin running edge AI. Think of it as KITT from Knight Rider, but real — the car talks to you about what it's feeling.",
  },
  {
    keywords: ["zeus", "aldc", "who built", "memory", "cloud", "analytic labs", "mission"],
    question: "Who built this?",
    answer:
      "KiSTI is built by Analytic Labs (ALDC) in collaboration with Boost Barn. ALDC's mission is to make data speak human — and KiSTI showcases that by bringing multiple technologies together, each with their own set of data, and making all of it as easy to interact with as having a conversation. Zeus is the cloud intelligence layer: pgvector-powered, 3.5M+ memories, AI-driven insights. Boost Barn handled the mechanical build — engine, turbo, fueling, ECU integration. Together, we wanted to bring the world of performance tuning together with modern data analytics.",
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
      "Officially? Knowledge-Integrated Smart Telemetry Interface. Truthfully? It stands for the Knight Industries STI — we're just kids who got older and needed a board-ready acronym. But there's a deeper layer: 'Ki' (気) is the Japanese concept of vital energy, the life force flowing through all living things. In KiSTI, data IS that vital energy — flowing through CAN buses, sensor wires, WiFi links, and cloud pipelines. The car literally channels its data-ki into something meaningful. Ki + STI. Data energy meets Subaru.",
  },
  {
    keywords: ["knight rider", "kitt", "talking car", "80s", "science fiction"],
    question: "Is this inspired by Knight Rider?",
    answer:
      "100%. We grew up as fans of Knight Rider. The idea of a talking car that understood its driver was science fiction in the 80s. KiSTI is our love letter to that idea — 19 sensors, 4 cameras, edge AI, and a memory system called Zeus that turns raw telemetry into plain English. Where KITT had an AI that could talk, KiSTI does all of that AND talks. It's not science fiction anymore — it's just good data engineering with a sense of humor.",
  },
  {
    keywords: ["data speak", "human", "mission", "purpose", "point", "demonstrate"],
    question: "What's the point of all this?",
    answer:
      "KiSTI is a vehicle — pun intended — built by Analytic Labs in collaboration with Boost Barn, to showcase what happens when you bring multiple technologies together, each with their own set of data. Our mission is to make data speak human. KiSTI shows off our ability to gather, analyze, and share data in novel and fun ways, while making all of it as easy to interact with as if you were having a conversation. Link gives us the nervous system, NVIDIA gives us the brain, Boost Barn gives us the muscle that delivers data fast. And Zeus ties it all together into plain English. Or in this case, plain racer.",
  },
  {
    keywords: ["business", "enterprise", "apply", "use case"],
    question: "Can this apply to business?",
    answer:
      "That's the whole point. Replace the sensors with databases, the cameras with APIs, the ECU with your data warehouse, and the Jetson with your AI layer — same architecture. Zeus is already used by enterprises to unify disparate data sources and make them speak human. KiSTI is just the most visceral demo: if we can make a race car talk, we can make your data talk too.",
  },
  {
    keywords: ["engine", "motor", "block", "iag", "short block", "ej257", "ej"],
    question: "What engine is in the car?",
    answer:
      "IAG Stage 750 short block — built for high cylinder pressure tolerance with a conservative operating strategy. Longevity is prioritized over peak output. Paired with the BCP X400 turbo, performance headers, high-flow downpipe, full exhaust, and an air/oil separator. The block has more ceiling than we're using — boost targets are deliberately conservative relative to what the 750 can handle. This is an engine built to last, not to impress a dyno.",
  },
  {
    keywords: ["horsepower", "hp", "power", "whp", "dyno", "output", "fast", "quick"],
    question: "How much power does it make?",
    answer:
      "On Shell 93 octane with the X400 turbo, IAG 750 block, FMIC, and full bolt-ons: estimated 360-390 wheel horsepower, roughly 430-460 at the crank. But here's the thing — we don't chase peak dyno numbers. The focus is area under the curve: midrange torque, transient response, and real-world 80-130 km/h passing performance. This car is built to feel fast everywhere, not just at redline.",
  },
  {
    keywords: ["awd", "drivetrain", "dccd", "differential", "diff", "all wheel"],
    question: "Tell me about the drivetrain.",
    answer:
      "Full-time AWD with Subaru's DCCD (Driver Controlled Center Differential). The GR chassis STI runs a proper mechanical center diff — you can bias torque front-to-rear on demand. With ~360-390 WHP going through all four wheels, it puts the power down in ways a RWD car can't. In the canyons, in the rain, on cold mornings — the AWD system is what makes this car usable year-round as a hot rod.",
  },
  {
    keywords: ["build", "philosophy", "why this", "concept", "strategy", "positioning"],
    question: "What's the build philosophy?",
    answer:
      "This is not a max-effort dyno car. Not a 500+ HP headline build. Not a top-end drag configuration. This is a midrange-dominant canyon car — a high-response AWD platform built for all-weather use. The goal is a cohesive, engineered feel, repeatable thermal performance, and a conservative tune that prioritizes response and area under the curve over peak numbers. A hot rod that happens to have data superpowers.",
  },
  {
    keywords: ["boost barn", "builder", "shop", "who built", "assembly", "install"],
    question: "Who built the car?",
    answer:
      "Boost Barn handled the full mechanical build: engine swap integration, turbo system installation, fueling hardware, FMIC plumbing, Link ECU integration, and calibration. Their approach is coherent system assembly — not piecemeal power chasing. Every component is chosen to work together, with reliability-forward setup and emphasis on drivability. They built it to be a cohesive machine, not a parts catalog bolted to a chassis.",
  },
  {
    keywords: ["cooling", "intercooler", "fmic", "heat", "thermal", "aos"],
    question: "How's the cooling setup?",
    answer:
      "Front-mount intercooler keeps intake temps stable even in sustained canyon runs. An air/oil separator prevents oil vapor from contaminating the intake. The whole cooling strategy is designed around repeatable thermal performance — this car needs to run hard for 30+ minutes without heat soak degrading power. Conservative boost targets relative to the IAG 750's capability give us thermal margin that most builds don't have.",
  },
  {
    keywords: ["intake", "maf", "speed density", "airflow", "induction"],
    question: "What intake setup does it run?",
    answer:
      "Speed density — no MAF sensor. With the FMIC, performance headers, high-flow downpipe, and full exhaust, removing the MAF gives the Link ECU cleaner control over fueling calculations. Speed density uses manifold pressure and air temp to calculate airflow, which is more stable with modified induction setups. Less restriction, fewer failure points, better tuning control.",
  },
  {
    keywords: ["launch", "acceleration", "0-60", "fast"],
    question: "Does it have launch control?",
    answer:
      "Yes — launch control is enabled through the Link ECU. It holds RPM at a target while the DCCD AWD system manages traction. Expect controlled wheelspin through 1st and into 2nd depending on surface. On Indy 500 street tires, the ~360-390 WHP will overwhelm grip pretty easily — launch control is less about maximum acceleration and more about managing the violence. The tune prioritizes tire management in 2nd and 3rd where the real canyon driving happens.",
  },
  {
    keywords: ["fuel", "gas", "octane", "shell", "93"],
    question: "What fuel does it run?",
    answer:
      "Shell 93 octane — the primary map. The entire tune is calibrated around consistent 93 octane operation with conservative ignition timing. No E85, no race gas dependencies. The philosophy is: if you can get it at a gas station, the car should run perfectly on it. That's part of the hot rod concept — it's a canyon monster you can daily without a fuel logistics plan.",
  },
  {
    keywords: ["boost barn", "shop", "who built", "builder", "aaron", "nijjar", "langley", "subaru shop", "specialty"],
    question: "Tell me about Boost Barn.",
    answer:
      "Boost Barn Motorsports is a Subaru specialty shop in Langley, BC, Canada. They help you accomplish your dream Subaru build from start to finish — parts, services, fabrication, dyno tuning, full start-to-finish projects, and maintenance. They're appointment-based only. They also handle regular maintenance and repairs on daily drivers and street cars. For KiSTI, Boost Barn handled the full mechanical build: IAG 750 short block, BCP X400 turbo install, fueling, FMIC plumbing, Link ECU integration, and calibration. Their philosophy is coherent system assembly — not piecemeal power chasing. They tune on Cobb, EcuTek, OpenSource, and standalone ECUs like Link, Ecumaster, Haltech, and AEM.",
  },
  {
    keywords: ["boost barn builds", "portfolio", "projects", "other builds", "clients"],
    question: "What else has Boost Barn built?",
    answer:
      "Boost Barn has a serious portfolio. Highlights: Kevin's 2008 STI with a Garrett G30-660 rotated turbo making 500 WHP on flex fuel — daily driven year-round including Canadian winters. Gurj's 2007 STI show car with a GTX3582R targeting 500-600 WHP, winner of car shows across Canada and the US. Rene's 2019 widebody STI 'Casper' — first 2015+ STI in Canada to run the Pandem Oiram kit, three-time first place and a national competition winner. And Aaron's own 2006 Baja drag build making 800 AWHP that ran a 10.8 at 121 mph. Every build is different, but the approach is the same: build it as a system, not a parts catalog.",
  },
  {
    keywords: ["contact", "phone", "email", "hours", "appointment", "location", "visit"],
    question: "How do I contact Boost Barn?",
    answer:
      "Boost Barn is appointment-only in Langley, BC. Phone: 604-613-4751. Email: info@boostbarnmotorsports.com. Hours are Tuesday through Friday 8am-5pm, Saturday 10am-5pm, closed Sunday and Monday. They don't publish their address publicly — contact them and they'll give you the location when you book. Find them on Instagram and Facebook at @boostbarnmotorsports.",
  },
  {
    keywords: ["dyno", "tuning", "tune", "cobb", "ecutek", "haltech", "standalone"],
    question: "Does Boost Barn do dyno tuning?",
    answer:
      "Yes — Boost Barn offers dyno tuning across multiple platforms: Cobb Accessport, EcuTek, OpenSource, and standalone ECUs including Link, Ecumaster, Vipec, AEM, and Haltech. For KiSTI, the Link G4X tune was done in-house with their 'one change at a time' logging discipline. They prioritize repeatable, heat-stable performance over chasing peak dyno numbers. If you're running a Subaru with any ECU platform, they can tune it.",
  },
];

export const STARTER_CHIPS = [
  "How much power does it make?",
  "What's the build philosophy?",
  "What's wrong with the FR brake?",
  "What does the name KiSTI mean?",
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
