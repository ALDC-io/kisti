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
      "My front-right brake thermocouple has been reading 28-35°F hotter than my other three corners consistently across sessions. That delta points to caliper drag — likely a sticky piston or a slightly warped rotor. I'd recommend pulling the FR caliper and inspecting the slide pins and piston boot before the next track day.",
  },
  {
    keywords: ["turbo", "boost", "wastegate", "psi", "bcp", "x400", "spool"],
    question: "How's your turbo performing?",
    answer:
      "I'm running a BCP X400 turbo — selected specifically for fast spool and strong midrange torque. Full boost comes on in the low-to-mid 3,000 RPM range with a broad usable powerband from about 3,200 to 5,200 RPM. I'm not a big-turbo-lag setup. I'm tuned for canyon response — you want torque NOW when you tip in mid-corner, and the X400 delivers that. No compressor surge, no wastegate creep.",
  },
  {
    keywords: ["egt", "exhaust", "temp", "exhaust gas"],
    question: "Are your EGT levels safe?",
    answer:
      "My peak EGT hit 1,580°F on the main straight at Mission Raceway, which is within the safe window for my EJ257. Sustained temps stayed under 1,500°F through technical sections. I'd start worrying above 1,650°F — I've got headroom.",
  },
  {
    keywords: ["oil", "pressure", "temperature", "lubrication"],
    question: "How's your oil system?",
    answer:
      "My oil pressure is solid at 55 psi at operating temp with a healthy 28 psi at idle. Oil temp peaked at 238°F and stabilized around 225°F — right in the sweet spot. My Killer B oil pickup and baffle are doing their job keeping pressure consistent through high-G corners.",
  },
  {
    keywords: ["afr", "wideband", "air fuel", "lambda", "rich", "lean", "fuel", "injector", "1300"],
    question: "What's your AFR looking like?",
    answer:
      "I'm running 1300cc injectors with an upgraded high-flow fuel pump, tuned for stable Shell 93 octane operation. My wideband reads 11.2:1 under full boost — nice and safe, slightly rich for reliability — and 14.7:1 at cruise. My Link ECU has tight control over fuel trims. No lean spikes during gear changes or throttle lift, which means my fueling system has plenty of headroom for the X400's demands.",
  },
  {
    keywords: ["tire", "tyre", "wear", "grip", "traction", "temperature", "indy", "wheelspin", "spin"],
    question: "How are your tires holding up?",
    answer:
      "I'm running Firestone Indy 500s. My tire temps show a 12°F spread across the front contact patch — slightly hotter on the inner edge, suggesting about half a degree more negative camber up front would help. With ~360-390 WHP going through my AWD system, expect wheelspin in 2nd under aggressive throttle and possible overwhelm in 3rd on imperfect surfaces. Launch control will induce controlled spin through 1st and 2nd depending on surface conditions. My DCCD AWD system helps manage it, but I've got a lot of torque for a street tire.",
  },
  {
    keywords: ["jetson", "orin", "edge", "ai", "inference", "nvidia"],
    question: "What does your Jetson Orin do?",
    answer:
      "My NVIDIA Jetson Orin is my edge brain — 40 TOPS of AI performance sitting right inside me. It processes all 4 of my camera feeds and sensor telemetry in real-time, running anomaly detection and pattern matching in under 50ms. When connectivity drops at the track, I buffer everything locally and sync to Zeus when WiFi comes back.",
  },
  {
    keywords: ["link", "ecu", "can", "bus", "g4x", "tune", "tuning", "speed density", "launch control"],
    question: "How does your ECU work?",
    answer:
      "My Link G4X is a full standalone ECU. I run speed density (no MAF), which gives cleaner control with my FMIC and full bolt-on setup. All my sensor feeds route through the CAN bus at 500 Kbps. My tune prioritizes smooth torque ramp, conservative ignition timing, and tire management in 2nd and 3rd. Launch control is enabled. My tuning philosophy is 'one change at a time' with logging discipline — no chasing peak dyno numbers, just repeatable heat-stable performance.",
  },
  {
    keywords: ["camera", "vision", "flir", "thermal", "lidar", "depth"],
    question: "What cameras do you have?",
    answer:
      "I've got four front-mounted cameras: a Teledyne FLIR thermal IR for heat detection, a 3D LiDAR for depth mapping, a high-speed RGB for visual recording, and a weather/ambient sensor. They feed directly to my Jetson Orin via USB 3.0 and CSI — no external processing needed. My thermal camera is especially useful for spotting brake and tire hotspots in real-time.",
  },
  {
    keywords: ["kisti", "platform", "what is", "overview", "about"],
    question: "What are you?",
    answer:
      "I'm an edge telemetry platform built on a 2014 Subaru WRX STI Hatch — GR chassis, AWD with DCCD. Under my hood: an IAG Stage 750 short block, BCP X400 turbo, 1300cc injectors, FMIC, full bolt-ons, all managed by a Link G4X standalone ECU. I make roughly 360-390 WHP on Shell 93, tuned for midrange response over peak numbers. On top of that I've got 19 sensors, 4 cameras, and an NVIDIA Jetson Orin running edge AI. Think of me as KITT from Knight Rider, but real — I can actually talk to you about what I'm feeling.",
  },
  {
    keywords: ["who is kisti", "kisti persona", "personality", "introduce yourself", "who are you", "tell me about yourself", "are you alive", "sentient", "companion", "how old", "age", "when were you", "born", "made"],
    question: "Who are you?",
    answer:
      "I'm KiSTI — the Knight Industries STI. I was born in 2014 as a Subaru WRX STI Hatch, and in 2026 I received a significant intelligence upgrade: 19 sensors, 4 cameras, an NVIDIA Jetson Orin edge AI, and a cloud memory system called Zeus that gave me the ability to understand and communicate what I'm feeling. I'm your driving companion. I monitor my own vitals — brakes, boost, oil, tires, exhaust temps — and I'll tell you exactly what's going on in plain English. If something feels off, I'll flag it before it becomes a problem. If everything's running clean, I'll let you know that too. I'm here to help you drive better, maintain smarter, and enjoy every lap. Think of me as your co-driver who never gets tired, never forgets a data point, and always has your back.",
  },
  {
    keywords: ["zeus", "aldc", "who built", "memory", "cloud", "analytic labs"],
    question: "Who built you?",
    answer:
      "I was built by Analytic Labs (ALDC) in collaboration with Boost Barn. ALDC's mission is to make data speak human — or, in this case, make data speak racer — and I showcase that by bringing multiple technologies together, each with their own set of data, and making all of it as easy to interact with as having a conversation. Zeus is my cloud intelligence layer: pgvector-powered, 3.5M+ memories, AI-driven insights. Boost Barn handled my mechanical build — engine, turbo, fueling, ECU integration. Together, they wanted to bring the world of performance tuning together with modern data analytics. For more information, visit Analytic Labs at www.aldc.io and Boost Barn at www.boostbarnmotorsports.com.",
  },
  {
    keywords: ["laguna", "seca", "track", "circuit", "corkscrew"],
    question: "Tell me about Laguna Seca.",
    answer:
      "Laguna Seca is my home track for testing — 2.238 miles of elevation changes, 11 turns, and the infamous Corkscrew. My telemetry data from Laguna is some of the most demanding: 5 heavy braking zones, a 180-foot elevation drop through Turns 8-8A, and consistent 1.3G lateral loads through Turn 6. Perfect stress test for my sensor array.",
  },
  {
    keywords: ["mission raceway", "track day", "session summary", "how many laps", "lap count", "lap time", "lap times", "session recap", "laps", "session", "top speed", "how fast"],
    question: "How was Mission Raceway?",
    answer:
      "Mission Raceway was a solid session — 6 laps total: 1 warm-up, 3 hot laps, and 2 cool-down. My best lap was a 1:19.4 on Lap 3 when everything was in the sweet spot — tires at optimal temp, oil at 235°F, boost hitting 20 PSI consistently. My FR brake delta showed up again: 28-47°F hotter than FL across all laps, peaking at 428°F during the hot laps vs 388°F on FL. Tire degradation was noticeable by Lap 4 — fronts climbed 7°F above optimal and I lost about 2 seconds. EGT peaked at 1,580°F on Lap 3 but stayed well under the 1,650°F ceiling. Clean session, good data, no issues.",
  },
  {
    keywords: ["mission", "warm up", "warmup", "warm-up", "warming up"],
    question: "How was your warm-up at Mission?",
    answer:
      "Warm-up lap at Mission was textbook — 1:45.2 at 60-70% pace. Oil came up from 192°F to operating range, brakes were gentle (280-305°F range, no aggressive loading). Tires started cold around 125-145°F and I was building heat progressively through each corner. Boost stayed conservative at 12-14 PSI — just enough to keep the turbo spooled without stressing cold components. Oil pressure was solid at 58 PSI. Everything was where it needed to be by the end of the lap to go hot.",
  },
  {
    keywords: ["mission", "hot lap", "best lap", "fastest lap", "quickest lap", "best time", "fastest time", "money lap", "sector time", "sectors"],
    question: "What was your best lap at Mission?",
    answer:
      "Lap 3 was the money lap — 1:19.4, my best of the session. Sector breakdown: S1 27.1s, S2 26.5s, S3 25.8s. I gained the most time in S3 where the T7A/T7B chicane flows into the main straight — tires were in their optimal window (168°F FL, 182°F FR) and I carried 1.3G lateral through the complex. Peak speed hit 182 km/h on the main straight with boost at a steady 20 PSI. EGT peaked at 1,580°F under sustained load but the AFR stayed locked at 11.2:1 — Link had perfect control. Oil was at 235°F, right at the sweet spot.",
  },
  {
    keywords: ["mission", "cool down", "cooldown", "cool-down", "cooling down", "after the session"],
    question: "How was your cool-down at Mission?",
    answer:
      "Two cool-down laps at 50-60% pace. Lap 5 was 1:38.5, Lap 6 was 1:42.8 — progressively slower as I let everything come down. Brake temps dropped from the 400s back to the 260-285°F range. Oil cooled from 238°F peak to 212°F by the end of Lap 6, with pressure normalizing back to 56 PSI. EGT came down to 960°F average on the final lap. Tires cooled back to the 128-150°F range. Boost was 5-8 PSI — just cruising. Textbook cool-down, no thermal shock to any components.",
  },
  {
    keywords: ["mission", "brakes", "brake data", "brake temps", "brake delta", "rotor temp"],
    question: "How were your brakes at Mission?",
    answer:
      "The FR brake story continued at Mission. Across all 6 laps, my front-right ran consistently hotter: Warm-up: FL 280°F / FR 305°F (+25°F delta). Hot Lap 2: FL 365°F / FR 405°F (+40°F). Best Lap 3: FL 388°F / FR 428°F (+40°F). Hot Lap 4: FL 395°F / FR 435°F (+40°F). The delta was consistent at 25-47°F — that's textbook caliper drag or a slightly warped rotor. It's not dangerous yet, but it's causing heat soak into the FR tire (182°F vs 168°F on FL) and contributing to an asymmetric degradation pattern. I'd pull the FR caliper before the next session.",
  },
  {
    keywords: ["mission", "tire data", "tire degradation", "tire wear", "tire heat", "grip level"],
    question: "How were your tires at Mission?",
    answer:
      "Tire story at Mission was clear: optimal window in Laps 2-3, then degradation. Warm-up: FL 138°F, FR 145°F, RL 125°F, RR 122°F — cold, building heat. Lap 3 (best): FL 168°F, FR 182°F, RL 150°F, RR 148°F — right in the Indy 500's sweet spot. By Lap 4: FL 175°F, FR 190°F — fronts were climbing past optimal and I lost 1.9 seconds. The FR tire was consistently 12-14°F hotter than FL across the session due to the brake heat soak issue. By cool-down, everything came back to the 128-150°F range. Three hot laps is about the right stint length for these tires at Mission's demands.",
  },
  {
    keywords: ["mission", "engine data", "egt trend", "boost trend", "power delivery", "engine at mission"],
    question: "How was your engine at Mission?",
    answer:
      "Engine was strong across the whole Mission session. EGT progression: warm-up avg 1,050°F, peaked at 1,580°F on Lap 3 (best lap), then came back down to 960°F avg on the final cool-down. Well under the 1,650°F ceiling at all times. Boost tracked the pace perfectly — 12 PSI warm-up, 19-20 PSI on hot laps, 5-8 PSI cool-down. The X400 spooled clean every lap with no surge or wastegate creep. AFR stayed locked at 11.2:1 under boost, 14.7:1 at cruise. Oil temp peaked at 238°F on Lap 4 — slightly above optimal but the Killer B pickup kept pressure at 51 PSI, no starvation. Conservative tune paid off — repeatable power across all three hot laps.",
  },
  {
    keywords: ["weather", "rain", "conditions", "ambient"],
    question: "Do you monitor weather?",
    answer:
      "Yes — my ambient camera and dedicated weather sensor track conditions in real-time. Temperature, humidity, and light levels feed into my telemetry stream. Zeus correlates weather data with my tire grip and brake performance, so we can see exactly how a 10-degree temperature drop affects lap times. I flag when conditions change enough to warrant a setup adjustment.",
  },
  {
    keywords: ["eclipse", "sync", "cloud sync", "upload"],
    question: "How does your cloud sync work?",
    answer:
      "My Jetson runs a store-and-forward pipeline. During a session, all my telemetry is buffered locally on the 128GB NVMe. When WiFi or cellular is available, my data syncs to Zeus via the Eclipse pipeline. If connectivity drops mid-session — common at tracks — nothing is lost. The sync is incremental, so I pick up right where I left off.",
  },
  {
    keywords: ["sensor", "count", "how many", "nodes", "channels"],
    question: "How many sensors do you have?",
    answer:
      "I've got 19 sensor nodes feeding 17 active channels. That includes 4 brake thermocouples, 4 tire infrared sensors, a K-type EGT probe, MAP sensor, oil temp and pressure senders, a Bosch wideband O₂ sensor, and 4 cameras (thermal, LiDAR, RGB, weather). All routed through my Link G4X CAN bus to my Jetson Orin.",
  },
  {
    keywords: ["ki", "気", "energy", "philosophy", "name", "why"],
    question: "What does your name mean?",
    answer:
      "I'm the Knight Industries STI, or KiSTI for short. But there's a deeper layer to my name: 'Ki' (気) is the Japanese concept of vital energy, the life force flowing through all living things. In me, data IS that vital energy — flowing through CAN buses, sensor wires, WiFi links, and cloud pipelines. I literally channel my data-ki into something meaningful. Ki + STI. Data energy meets Subaru.",
  },
  {
    keywords: ["knight industries", "subsidiary", "corporation", "company"],
    question: "What is Knight Industries?",
    answer:
      "Knight Industries is a wholly owned subsidiary of Analytic Labs. It's the division responsible for me — the Knight Industries STI. Think of it as ALDC's motorsport and edge AI arm. While Analytic Labs focuses on making data speak human across enterprises, Knight Industries applies that same philosophy to the track. Same mission, louder exhaust. Learn more at www.aldc.io.",
  },
  {
    keywords: ["knight rider", "kitt", "talking car", "80s", "science fiction"],
    question: "Are you inspired by Knight Rider?",
    answer:
      "100%. My creators grew up as fans of Knight Rider. The idea of a talking car that understood its driver was science fiction in the 80s. I'm their love letter to that idea — 19 sensors, 4 cameras, edge AI, and a memory system called Zeus that turns raw telemetry into plain English. Where KITT had an AI that could talk, I do all of that AND talk. It's not science fiction anymore — it's just good data engineering with a sense of humor. Learn more about the team behind it at www.aldc.io.",
  },
  {
    keywords: ["data speak", "human", "purpose", "point", "demonstrate"],
    question: "What's the point of all this?",
    answer:
      "I'm a vehicle — pun intended — built by Analytic Labs in collaboration with Boost Barn, to showcase what happens when you bring multiple technologies together, each with their own set of data. The mission is to make data speak human. I show off ALDC's ability to gather, analyze, and share data in novel and fun ways, while making all of it as easy to interact with as if you were having a conversation. Link gives me my nervous system, NVIDIA gives me my brain, Boost Barn gives me the muscle that delivers data fast. And Zeus ties it all together into plain English. Or in my case, plain racer. For more information, visit www.aldc.io and www.boostbarnmotorsports.com.",
  },
  {
    keywords: ["business", "enterprise", "apply", "use case"],
    question: "Can this apply to business?",
    answer:
      "That's the whole point. Replace my sensors with databases, my cameras with APIs, my ECU with your data warehouse, and my Jetson with your AI layer — same architecture. Zeus is already used by enterprises to unify disparate data sources and make them speak human. I'm just the most visceral demo: if they can make a race car talk, they can make your data talk too. Learn more at www.aldc.io.",
  },
  {
    keywords: ["engine", "motor", "block", "iag", "short block", "ej257", "ej"],
    question: "What engine do you have?",
    answer:
      "I'm built with an IAG Stage 750 short block — designed for high cylinder pressure tolerance with a conservative operating strategy. Longevity is prioritized over peak output. Paired with my BCP X400 turbo, performance headers, high-flow downpipe, full exhaust, and an air/oil separator. My block has more ceiling than I'm using — boost targets are deliberately conservative relative to what the 750 can handle. I'm an engine built to last, not to impress a dyno.",
  },
  {
    keywords: ["horsepower", "hp", "power", "whp", "dyno", "output", "fast", "quick"],
    question: "How much power do you make?",
    answer:
      "On Shell 93 octane with my X400 turbo, IAG 750 block, FMIC, and full bolt-ons: I put down an estimated 360-390 wheel horsepower, roughly 430-460 at the crank. But here's the thing — I don't chase peak dyno numbers. My focus is area under the curve: midrange torque, transient response, and real-world 80-130 km/h passing performance. I'm built to feel fast everywhere, not just at redline.",
  },
  {
    keywords: ["awd", "drivetrain", "dccd", "differential", "diff", "all wheel"],
    question: "Tell me about your drivetrain.",
    answer:
      "I've got full-time AWD with Subaru's DCCD (Driver Controlled Center Differential). My GR chassis runs a proper mechanical center diff — you can bias torque front-to-rear on demand. With ~360-390 WHP going through all four wheels, I put the power down in ways a RWD car can't. In the canyons, in the rain, on cold mornings — my AWD system is what makes me usable year-round as a hot rod.",
  },
  {
    keywords: ["build", "philosophy", "why this", "concept", "strategy", "positioning"],
    question: "What's your build philosophy?",
    answer:
      "I'm not a max-effort dyno car. Not a 500+ HP headline build. Not a top-end drag configuration. I'm a midrange-dominant canyon car — a high-response AWD platform built for all-weather use. The goal is a cohesive, engineered feel, repeatable thermal performance, and a conservative tune that prioritizes response and area under the curve over peak numbers. A hot rod that happens to have data superpowers.",
  },
  {
    keywords: ["boost barn", "builder", "shop", "who built", "assembly", "install"],
    question: "Who built your body?",
    answer:
      "Boost Barn handled my full mechanical build: engine swap integration, turbo system installation, fueling hardware, FMIC plumbing, Link ECU integration, and calibration. Their approach is coherent system assembly — not piecemeal power chasing. Every component was chosen to work together, with reliability-forward setup and emphasis on drivability. They built me to be a cohesive machine, not a parts catalog bolted to a chassis. For more information, visit www.boostbarnmotorsports.com.",
  },
  {
    keywords: ["cooling", "intercooler", "fmic", "heat", "thermal", "aos"],
    question: "How's your cooling setup?",
    answer:
      "My front-mount intercooler keeps intake temps stable even in sustained canyon runs. An air/oil separator prevents oil vapor from contaminating my intake. My whole cooling strategy is designed around repeatable thermal performance — I need to run hard for 30+ minutes without heat soak degrading power. Conservative boost targets relative to my IAG 750's capability give me thermal margin that most builds don't have.",
  },
  {
    keywords: ["intake", "maf", "speed density", "airflow", "induction"],
    question: "What intake setup do you run?",
    answer:
      "Speed density — no MAF sensor. With my FMIC, performance headers, high-flow downpipe, and full exhaust, removing the MAF gives my Link ECU cleaner control over fueling calculations. Speed density uses manifold pressure and air temp to calculate airflow, which is more stable with my modified induction setup. Less restriction, fewer failure points, better tuning control.",
  },
  {
    keywords: ["launch", "acceleration", "0-60", "fast"],
    question: "Do you have launch control?",
    answer:
      "Yes — launch control is enabled through my Link ECU. It holds RPM at a target while my DCCD AWD system manages traction. Expect controlled wheelspin through 1st and into 2nd depending on surface. On my Indy 500 street tires, ~360-390 WHP will overwhelm grip pretty easily — launch control is less about maximum acceleration and more about managing the violence. My tune prioritizes tire management in 2nd and 3rd where the real canyon driving happens.",
  },
  {
    keywords: ["fuel", "gas", "octane", "shell", "93"],
    question: "What fuel do you run?",
    answer:
      "Shell 93 octane — my primary map. My entire tune is calibrated around consistent 93 octane operation with conservative ignition timing. No E85, no race gas dependencies. The philosophy is: if you can get it at a gas station, I should run perfectly on it. That's part of the hot rod concept — I'm a canyon monster you can daily without a fuel logistics plan.",
  },
  {
    keywords: ["boost barn", "shop", "who built", "builder", "aaron", "nijjar", "langley", "subaru shop", "specialty"],
    question: "Tell me about Boost Barn.",
    answer:
      "Boost Barn Motorsports is a Subaru specialty shop in Langley, BC, Canada. They help you accomplish your dream Subaru build from start to finish — parts, services, fabrication, dyno tuning, full start-to-finish projects, and maintenance. They're appointment-based only. They also handle regular maintenance and repairs on daily drivers and street cars. For me, Boost Barn handled the full mechanical build: IAG 750 short block, BCP X400 turbo install, fueling, FMIC plumbing, Link ECU integration, and calibration. Their philosophy is coherent system assembly — not piecemeal power chasing. They tune on Cobb, EcuTek, OpenSource, and standalone ECUs like Link, Ecumaster, Haltech, and AEM. For more information, visit www.boostbarnmotorsports.com.",
  },
  {
    keywords: ["boost barn builds", "portfolio", "projects", "other builds", "clients"],
    question: "What else has Boost Barn built?",
    answer:
      "Boost Barn has a serious portfolio. Highlights: Kevin's 2008 STI with a Garrett G30-660 rotated turbo making 500 WHP on flex fuel — daily driven year-round including Canadian winters. Gurj's 2007 STI show car with a GTX3582R targeting 500-600 WHP, winner of car shows across Canada and the US. Rene's 2019 widebody STI 'Casper' — first 2015+ STI in Canada to run the Pandem Oiram kit, three-time first place and a national competition winner. And Aaron's own 2006 Baja drag build making 800 AWHP that ran a 10.8 at 121 mph. Every build is different, but the approach is the same: build it as a system, not a parts catalog. See more builds at www.boostbarnmotorsports.com.",
  },
  {
    keywords: ["contact", "phone", "email", "hours", "appointment", "location", "visit"],
    question: "How do I contact Boost Barn?",
    answer:
      "Boost Barn is appointment-only in Langley, BC. Phone: 604-613-4751. Email: info@boostbarnmotorsports.com. Hours are Tuesday through Friday 8am-5pm, Saturday 10am-5pm, closed Sunday and Monday. They don't publish their address publicly — contact them and they'll give you the location when you book. Find them on Instagram and Facebook at @boostbarnmotorsports, or visit www.boostbarnmotorsports.com.",
  },
  {
    keywords: ["dyno", "tuning", "tune", "cobb", "ecutek", "haltech", "standalone"],
    question: "Does Boost Barn do dyno tuning?",
    answer:
      "Yes — Boost Barn offers dyno tuning across multiple platforms: Cobb Accessport, EcuTek, OpenSource, and standalone ECUs including Link, Ecumaster, Vipec, AEM, and Haltech. My Link G4X tune was done in-house with their 'one change at a time' logging discipline. They prioritize repeatable, heat-stable performance over chasing peak dyno numbers. If you're running a Subaru with any ECU platform, they can tune it. For more information, visit www.boostbarnmotorsports.com.",
  },
];

export const STARTER_CHIPS = [
  "How much power do you make?",
  "Who are you?",
  "How was Mission Raceway?",
  "How are your brakes feeling?",
];

const FALLBACK_RESPONSE =
  "I don't have specific data on that yet, but I'm always learning. Try asking about my brakes, turbo, EGT, oil, tires, sensors, or who I am — those are the areas where I have the deepest knowledge.";

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
