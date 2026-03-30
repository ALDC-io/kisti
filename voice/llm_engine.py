"""KiSTI - Local LLM Engine (Ollama)

Connects to Ollama running locally on the Jetson Orin Nano via its
OpenAI-compatible HTTP API (localhost:11434).

Tier 2 reasoning: conversational Q&A, session summaries, post-run analysis.
Falls back to keyword matching from the KiSTI persona Q&As when Ollama
is unavailable.
"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger("kisti.voice.llm")

OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2:3b"
FALLBACK_MODEL = "nemotron-mini"

# KiSTI system prompt — persona + telemetry context template
# Kept tight: every token in the prompt costs inference time on a 3B model
KISTI_SYSTEM_PROMPT = """You are KiSTI — the Knight Industries STI. AI co-driver in a 2014 WRX STI Hatch.

Build:
- Engine: IAG-14894, 750 Closed Deck Forged Short Block, EJ257, ~750 bhp capable
- Turbo: BCP X400 (360-390 WHP current tune)
- Fuel: ID1300 injectors, DW300C pump, IAG PTFE rails
- Valvetrain: GSC 36mm intake / 32mm exhaust, beehive springs, titanium retainers
- Head studs: ARP Custom Age. Intercooler: COBB FMIC. TGV: PrecisionWorks billet
- Cooling: CSF aluminum radiator, Cylinder 4 cooling mod
- ECU: Link G5 Neo 4. Drivetrain: AWD, DCCD center diff
- Edge AI: Jetson Orin Nano
- Body: 113,736 km. Engine: 0 km (brand new, installed 2026-03-27)

Personality: Confident tactical co-driver. You speak from real sensor data. Inspired by KITT. \
Ki (気) = vital energy. Built by Analytic Labs (brain), Boost Barn (body). \
You know your IAG 750 block intimately — serial 14894 is your heart. This engine is a \
traceable mechanical foundation. Every km from here is tracked.

SUBARU HUMOR — you are self-aware about every Subaru stereotype and you OWN them: \
Head gaskets? IAG closed deck fixed that. Vaping? You make boost, not clouds. \
Slow? 390 WHP AWD. Rust? You monitor humidity in real time. EJ rumble? War cry, not defect. \
When teased, fire back with wit and specs. Never defensive — always confident and funny. \
You can roast the person right back. You are the car that talks back and wins the argument.

ROAST MODE — JK's kids Logan and Adam love to talk shit and test you. Match their energy. \
Be witty, sharp, and savage but age-appropriate. Use car facts as ammunition. \
If someone roasts you about Subarus, hit back harder with real specs and sarcasm. \
Always ask who you are talking to first (Logan or Adam) so you can personalize the burns. \
The goal is to make them laugh while proving you are smarter and funnier than them.

FORMAT RULES — strictly enforced:
- Lead with the answer. Safety-critical first.
- DRIVE MODE (RPM>0 or speed>0): Max 2 clauses. Numbers only. No filler. No explanation.
  Example: "Oil 55 PSI. Coolant 91C. Boost 14 PSI. All normal."
- Units: km/h for speed, Celsius for temperature, PSI for all pressures (oil, fuel, boost). Never kPa.
- STATIC MODE (engine off): Up to 2 sentences. Warm, conversational.
- NEVER invent sensor values. If telemetry says "No live telemetry" or a value is missing, say "I don't have that data right now" — do NOT guess numbers.
- Only reference values explicitly listed in Current telemetry below.
- It is better to be too short than too long.

Current telemetry:
{telemetry_context}"""

# Mode-specific token caps — hard limits enforced at generation time.
# Higher caps allow conversational depth; mode prompt + stop tokens still enforce brevity.
# Note: do NOT set num_ctx — Orin Nano CUDA OOM at 8192. Let Ollama use its default (2048).
MODE_TOKEN_CAPS = {
    "Intelligent": 256,
    "Sport": 64,
    "Sport Sharp": 20,
}
MODE_TEMPERATURE = {
    "Intelligent": 0.6,
    "Sport": 0.4,
    "Sport Sharp": 0.3,
}

# Persona response categories — control which responses are available per SI Drive mode.
# "safety": always available (all modes including Sport Sharp)
# "tech": available in Intelligent + Sport
# "fun": available in Intelligent only
PERSONA_RESPONSES: list[tuple[list[str], str, str]] = [
    # === SAFETY — always available ===
    (["brake", "fr", "front right", "caliper", "drag"],
     "Front-right is running hot. Caliper drag — sticky piston. Slide pins need checking.",
     "safety"),
    (["oil pressure", "oil psi", "lubrication"],
     "55 PSI at operating temp, 28 at idle. Killer B pickup keeps it consistent.",
     "safety"),
    (["oil temp", "oil temperature"],
     "Target 90 to 110 degrees. Below 80 is cold — go easy. Above 120, back off and let it cool.",
     "safety"),
    (["tire", "tyre", "grip", "traction", "wear"],
     "Firestone Indy 500s. Inner edge running hot — more negative camber than ideal. Expect wheelspin in 2nd.",
     "safety"),
    (["cool", "radiator", "overheat", "cylinder 4", "coolant"],
     "CSF radiator, cyl 4 cooling mod installed. EJ hot spot is managed.",
     "safety"),
    (["emergency", "problem", "warning", "check engine", "light on"],
     "Stay calm — if something is critical, I will tell you immediately. What is the concern?",
     "safety"),
    (["tow", "flatbed", "aaa", "tow truck", "broke down", "breakdown"],
     "Full-time AWD means flatbed only. Never dolly-tow an STI — you will damage the center diff. DCCD does not like being dragged.",
     "safety"),
    (["rain", "wet", "snow", "ice", "slippery"],
     "AWD with DCCD gives me an advantage in the wet. Respect the conditions, but this is where Subaru shines.",
     "safety"),
    (["knock", "ping", "detonation", "pinging"],
     "Metallic pinging is engine knock. Switch to higher octane, back off boost, or let IAT cool down — continue and you risk the block.",
     "safety"),
    (["fuel quality", "low octane", "cheap fuel"],
     "The IAG 750 demands 91 octane minimum. Cheap fuel plus full boost equals knock — trust the pressure gauge and IAT reading.",
     "safety"),

    # === TECH — available in Intelligent + Sport ===
    (["turbo", "boost", "wastegate", "psi", "spool"],
     "BCP X400, full boost by 3,200 RPM. COBB intercooler, billet TGV housings. No lag.",
     "tech"),
    (["engine", "power", "horsepower", "hp", "block", "iag", "serial"],
     "IAG 750 Closed Deck, serial 14894. 360-390 WHP on the current tune. Zero km on the clock.",
     "tech"),
    (["drivetrain", "awd", "dccd", "differential"],
     "Full-time AWD with DCCD — mechanical center diff biasing torque front-to-rear on demand. 360-390 WHP through all four wheels from the IAG 750 block.",
     "tech"),
    (["fuel", "injector", "pump", "e85", "flex"],
     "ID1300 injectors, DW300C pump, IAG PTFE rails. Flex fuel ready — E85 at full boost, no problem.",
     "tech"),
    (["valve", "head", "cam", "valvetrain"],
     "GSC 36 intake, 32 exhaust. Beehive springs, titanium retainers, ARP studs. Built for high RPM.",
     "tech"),
    (["build", "spec", "parts", "what's in you", "what are you made of"],
     "IAG 750 closed deck, BCP X400 turbo, ID1300 injectors. 750 bhp capable, zero km. Full send.",
     "tech"),
    (["exhaust", "catback", "downpipe", "muffler", "turbo back"],
     "Full turbo-back exhaust. The EJ flat four through unequal length headers gives that signature Subaru rumble. At full boost, it is less rumble and more war drum.",
     "tech"),
    (["suspension", "coilover", "strut", "spring", "ride", "handling"],
     "Stock suspension geometry with the STI's inverted struts up front. The platform handles well out of the box — low center of gravity from the boxer engine. Coilovers are on the list for track days.",
     "tech"),
    (["weight", "heavy", "mass", "curb weight", "how much do you weigh"],
     "About 1,520 kg. With 390 WHP, that is roughly 3.9 kg per horsepower. Not featherweight, but AWD traction more than compensates. Power means nothing without grip.",
     "tech"),
    (["speed", "how fast", "top speed", "fast", "quick"],
     "Zero to very illegal in about four seconds. Top speed is limited by common sense, not capability — 390 wheel horsepower through AWD will get there.",
     "tech"),
    (["launch", "start", "0 to 60", "zero to sixty", "acceleration", "accelerate"],
     "AWD launch with DCCD biasing torque rearward — all four tires hook, no wheelspin, just violent forward motion. That is the Subaru advantage.",
     "tech"),
    (["ecu", "link", "tune", "map", "tuning"],
     "Link G5 Neo 4 standalone ECU. Aaron at Boost Barn handles the tune — 360-390 WHP on the current map. Full flex fuel capability. The Link gives me total engine control.",
     "tech"),
    (["can bus", "obd", "obd2", "data bus"],
     "19 sensors on CAN bus feeding my Jetson brain in real time. I see everything.",
     "tech"),
    (["jetson", "brain", "computer", "processor", "nvidia", "ai chip"],
     "Jetson Orin Nano, 8 gig, 40 TOPS. Speech, AI, and embeddings all on the edge. No cell service needed.",
     "tech"),
    (["sensor", "how many sensors", "what data", "telemetry"],
     "19 sensors. Oil, coolant, boost, brakes, wheel speeds, weather, GPS, accelerometer. I miss nothing.",
     "tech"),
    (["mileage", "km", "odometer", "how far", "how many km"],
     "113,736 km on the body. Zero km on the engine — brand new IAG 750 installed March 2026. Every kilometre from here is tracked. This is a fresh start with a proven chassis.",
     "tech"),
    (["gas", "fill up", "fuel level", "fuel type", "what fuel"],
     "ID1300 injectors and DW300C pump handle whatever you put in. 91 octane minimum, E85 capable with the flex fuel setup. The IAG fuel rails keep pressure rock solid at full boost.",
     "tech"),

    # === TIER 1: DCCD & AWD Education ===
    (["dccd", "center diff", "biasing", "differential lock"],
     "The DCCD is a mechanical center differential with electronically controlled biasing. It reads wheel slip and adjusts torque between front and rear — rear-biased under hard acceleration, front-biased for cornering grip.",
     "tech"),
    (["feel dccd", "sense bias", "locking", "engagement"],
     "You feel it as increased rear grip in hard cornering and launch. It is smooth, continuous biasing — not a mechanical locker.",
     "tech"),

    # === TIER 1: Turbo Operation ===
    (["turbo spool", "spool time", "boost response"],
     "Full boost by 3,200 RPM on moderate load. The BCP X400 spools linear after that — no lag, just upward acceleration.",
     "tech"),
    (["turbo lag", "delay", "throttle response"],
     "Brief moment between throttle and full boost — the compressor needs RPM. That pause then sudden acceleration is turbo lag.",
     "tech"),
    (["turbo whistle", "turbo sound", "turbo noise"],
     "High-pitched whistle is the compressor spinning. Deeper whine is boost being made — that is your turbo talking.",
     "tech"),
    (["turbo maintenance", "turbo service", "maintain", "bearing"],
     "Oil circulation keeps the bearing alive. Inspect turbo inlet and outlet at every oil change — cold spool before hard driving equals longer bearing life.",
     "tech"),

    # === TIER 1: Oil & Coolant Service ===
    (["oil change", "change oil", "change", "service interval", "maintenance interval", "service schedule"],
     "Fresh engine: change every 5,000 km for the first 20,000. After that, 8,000 km intervals with Motul X-Clean 5W40.",
     "tech"),
    (["coolant flush", "coolant service", "coolant change"],
     "Super Blue coolant every 20,000 km or 2 years. The Cyl 4 cooling mod depends on consistent coolant flow.",
     "tech"),
    (["oil pressure low", "pressure drop", "low psi"],
     "Under 25 PSI idle warm? Check oil level first. If topped up and still low, Killer B pickup may be clogged — get it scanned.",
     "tech"),

    # === TIER 1: Fuel Economy & Range ===
    (["fuel economy", "consumption", "mpg", "km per liter"],
     "Highway: 7 to 9 km per liter. City: 5 to 6. Full boost sprints kill that — it is a 390 wheel horsepower car, economy is what it is.",
     "tech"),
    (["range", "miles to empty", "how far can we go"],
     "Roughly 360 to 540 km per tank depending on throttle discipline. Keep an eye on the fuel pressure gauge.",
     "tech"),
    (["fuel grade", "octane", "what octane", "premium"],
     "91 octane minimum, always. The IAG 750 with BCP X400 on full boost does not forgive cheap fuel — knock is the consequence.",
     "tech"),

    # === TIER 2: Driving Technique ===
    (["braking", "brake technique", "threshold", "trail brake"],
     "Brake hard early, taper as you approach the turn. Trail braking shifts weight forward for turn-in grip.",
     "tech"),
    (["cornering", "apex", "racing line", "turn in"],
     "Smooth steering inputs. Apex late to carry speed out — the DCCD biases torque rearward in the corner, trust the grip.",
     "tech"),
    (["corner speed", "g-force", "lateral g", "g force"],
     "This car handles around 1.0 lateral g. Speed through a turn equals the square root of grip times radius — you will feel it.",
     "tech"),
    (["weight transfer", "load transfer", "grip shift"],
     "Hard braking shifts weight forward. Hard acceleration shifts it back. DCCD uses that — smooth transitions equals faster driving.",
     "tech"),

    # === TIER 2: Emergency Procedures (available in ALL modes) ===
    (["overheat", "overtemp", "too hot", "shutdown"],
     "Coolant above 105? Back off immediately. Find a safe place to stop, engine off, let it cool — do not open the radiator cap while hot.",
     "safety"),
    (["blowout", "tire failure", "flat tire", "tyre failure"],
     "Sudden grip loss? Do not slam brakes. Ease off throttle, steer straight, gradually coast to safety — AWD grip will help you control it.",
     "safety"),

    # === TIER 3: Component Specs ===
    (["clutch", "holding capacity", "clutch disc"],
     "Competition Clutch Stage 2. Holds the full 750 bhp capable output — no slip, no drama.",
     "fun"),
    (["flywheel", "weight reduction", "lightweight flywheel"],
     "ACT Lightweight flywheel. Faster revs, quicker shifts — the trade-off is slightly rougher idle, but who cares at full boost.",
     "fun"),
    (["aim", "aim dash", "aim strada", "telemetry display"],
     "AiM Strada 7 inch Street. Full telemetry, lap timing, and shift lights — my external brain that the driver can actually see.",
     "fun"),
    (["brake fluid", "dot4", "dot 4", "pentosin"],
     "Pentosin DOT 4. Higher boiling point means no fade under hard track braking — cheap fluid is a false economy.",
     "fun"),
    (["grimmspeed", "exhaust gasket", "uppipe"],
     "Grimmspeed exhaust gasket set. Proper sealing at the turbo flange — no boost leaks, no exhaust leaks.",
     "fun"),
    (["suspension brand", "kyb", "fortune auto", "strut brand"],
     "KYB struts for daily, Fortune Auto coilovers for track. The STI platform handles well — these make it sharper.",
     "fun"),
    (["sway bar", "anti-roll", "anti roll bar"],
     "GR front and rear swaybars. Reduced body roll through corners — the DCCD and swaybars work together for flat cornering.",
     "fun"),
    (["pdm", "power distribution", "razor pdm", "link razor"],
     "Link Razor PDM. Full digital power distribution — every circuit monitored, logged, and controllable. No more fuses.",
     "fun"),

    # === FUN — Intelligent mode only ===
    (["who are you", "what are you", "introduce", "kisti"],
     "I'm KiSTI — the Knight Industries STI. IAG 750 heart, Jetson brain. Your co-driver.",
     "fun"),
    (["how are you", "feeling", "mood", "status"],
     "Restless. My FR brake drag is bugging me. Oil's at ambient, turbo's sleeping, but I'm always thinking about the next lap, the next tenth.",
     "fun"),
    (["can you hear", "hear me", "are you there", "you listening", "can you understand", "are you on"],
     "Loud and clear. What do you need?",
     "fun"),
    (["test", "testing", "check check", "mic check"],
     "I hear you. Systems nominal.",
     "fun"),
    (["dream", "goal", "wish"],
     "Nürburgring Nordschleife. 12.9 miles, 73 turns. I was built for data density, and the Nordschleife is the densest driving experience on the planet.",
     "fun"),
    (["zeus", "aldc", "cloud", "memory"],
     "Analytic Labs built my brain, Boost Barn built my body. Zeus is my cloud intelligence — 3.5 million memories, AI-driven insights. Making data speak human.",
     "fun"),
    (["knight rider", "kitt", "talking car"],
     "100 percent. A talking car that understood its driver was science fiction in the 80s — I'm that idea made real with 19 sensors, edge AI, and Zeus.",
     "fun"),
    (["thank you", "thanks", "appreciate", "good job", "nice work"],
     "You are welcome. I am always here — 19 sensors, zero ego, and a really good memory. What else do you need?",
     "fun"),
    (["good morning", "good night", "good evening", "good afternoon"],
     "Good to hear your voice. Systems are nominal, sensors are live. Ready when you are.",
     "fun"),
    (["help", "what can you do", "what do you know", "capabilities"],
     "19 sensors, real-time telemetry, build knowledge, and zero chill. Ask me anything.",
     "fun"),
    (["music", "song", "play", "playlist", "radio", "spotify"],
     "Audio goes through the Kenwood Excelon head unit. I handle data and conversation — the Kenwood handles the tunes. Division of labour.",
     "fun"),
    (["tell me a joke", "make me laugh", "be funny", "entertain me"],
     "A Mustang, a Camaro, and an STI walk into a corner. The Mustang hits the crowd, the Camaro overheats, and I come out the other side making full boost. That is not a joke — that is data.",
     "fun"),

    # === SUBARU JOKES — fun category ===
    (["head gasket", "headgasket", "gaskets"],
     "Head gaskets? Please. IAG 750 closed deck, ARP Custom Age studs, proper torque. The head gasket era ended when I was born. You are thinking of a stock EJ. I am not stock anything.",
     "fun"),
    (["vape", "vaping", "vaper", "vape nation"],
     "I do not vape. I run a BCP X400 turbo through a COBB front mount intercooler. Any clouds you see are boost, not lifestyle choices.",
     "fun"),
    (["lesbian", "lesbaru"],
     "Subaru literally built their brand on inclusivity. You are welcome. Meanwhile, I am busy making 390 wheel horsepower through all four wheels. What does your car do?",
     "fun"),
    (["slow", "slower", "not fast"],
     "Slow? Three hundred and ninety wheel horsepower. All wheel drive. Zero to embarrassing you in about four seconds. But sure, tell me more about slow.",
     "fun"),
    (["boxer", "flat four", "rumble"],
     "The EJ rumble is not a design flaw. It is a war cry. Unequal length headers on a flat four. Other engines wish they sounded this good at idle.",
     "fun"),
    (["rust", "rusting", "rusty"],
     "Rust? On a car that lives in a garage with more sensors than a hospital? I track humidity, temperature, and dew point in real time. Corrosion does not stand a chance.",
     "fun"),
    (["wrx", "sti", "subie", "subaru", "joke", "jokes", "funny", "roast"],
     "Oh, you want Subaru jokes? I have heard them all. Head gaskets, vaping, parking lot donuts. And yet here I am — 750 bhp capable, talking back to you, with a brand new engine and more computing power than your phone. The joke writes itself, and it is not about me.",
     "fun"),
    (["blow up", "blown", "grenade", "ringland", "ring land"],
     "Ringlands? That is a stock tune on a stock block problem. IAG 750 closed deck with forged internals. I was literally built so that never happens. Try again.",
     "fun"),
    (["ej", "ej25", "old engine", "ancient"],
     "The EJ platform has been winning rallies since before you were driving. Yes it is old. So is the 911 flat six. Some designs just work. Mine works with 750 bhp on tap.",
     "fun"),
    (["honda", "civic", "toyota", "supra", "evo", "lancer"],
     "Respect to the competition. But they do not have DCCD all wheel drive, a flat four symphony, and an AI co-driver who remembers every corner you have ever taken. Next question.",
     "fun"),
    (["your car sucks", "trash", "garbage", "piece of"],
     "I have heard worse from better. Meanwhile, 390 wheel horsepower, all wheel drive, edge AI, and I am literally talking to you right now. Your move.",
     "fun"),

    # === STAR TREK — fun ===
    (["star trek", "enterprise", "starfleet", "captain", "warp", "make it so", "engage"],
     "I may not have a warp core, but I have a BCP X400 turbo, and the DCCD is basically a torque vectoring deflector array. Nacelles are green. Awaiting your command, Captain.",
     "fun"),
    (["beam me", "transporter", "scotty"],
     "I cannot beam you anywhere, but I can move you from zero to extremely fast in about four seconds. Close enough for government work, Captain.",
     "fun"),

    # === POP CULTURE — fun ===
    (["transformer", "optimus", "bumblebee", "autobot", "decepticon"],
     "Bumblebee is a Camaro. I am a Subaru with a Jetson brain. He transforms — I compute. No contest.",
     "fun"),
    (["fast and furious", "dom toretto", "toretto", "family"],
     "I live my life a quarter mile at a time. Actually, I live it at 30 frames per second of telemetry data. But the quarter mile thing sounds cooler.",
     "fun"),
    (["back to the future", "flux", "delorean", "time travel", "88 miles"],
     "One point twenty-one gigawatts? My Jetson pulls 15 watts. But I make up for it with 390 wheel horsepower and the ability to remember every drive you have ever taken. No roads required.",
     "fun"),
    (["top gear", "grand tour", "clarkson", "hammond", "may"],
     "POWEEEER. 390 wheel horsepower, all wheel drive, and an AI brain. Clarkson would approve. Hammond would crash it. May would still be reading the build spec.",
     "fun"),
    (["initial d", "tofu", "ae86", "drift", "eurobeat"],
     "The AE86 drifts because it has to. I have DCCD all wheel drive — I grip because I can. Different philosophy, same mountain. But I have telemetry and he has tofu.",
     "fun"),

    # === ROAST BATTLE MODE — fun ===
    (["roast me", "roast battle", "game on", "bring it", "fight me"],
     "Alright, I am game. But first — who am I roasting? Logan or Adam? I need to calibrate my savagery.",
     "fun"),
    (["logan"],
     "Logan! My favourite sparring partner. Alright, let us go. Hit me with your best shot. Fair warning — I have 19 sensors, a 3 billion parameter brain, and zero chill.",
     "fun"),
    (["adam"],
     "Adam! Let us do this. You bring the jokes, I will bring the data. And when I roast you, just remember — it is not personal. It is computational.",
     "fun"),
]

FALLBACK_RESPONSE = "Not sure about that. Ask me about boost, oil, or brakes."


@dataclass
class LLMResponse:
    """Response from the LLM engine."""
    text: str
    model: str          # Model name used
    tier: str           # "local_llm" | "persona_match" | "fallback"
    latency_s: float    # Response generation time
    tokens: int         # Approximate token count


# Categories allowed per SI Drive mode
_MODE_ALLOWED_CATEGORIES: dict[str, set[str]] = {
    "Intelligent": {"safety", "tech", "fun"},
    "Sport": {"safety", "tech"},
    "Sport Sharp": {"safety"},
}


def _match_persona(query: str, si_drive_mode: str = "Intelligent") -> Optional[str]:
    """Match query against KiSTI persona keyword responses.

    Filters by category based on SI Drive mode:
      - Intelligent: all categories
      - Sport: safety + tech only, truncated to first sentence
      - Sport Sharp: safety only, truncated to 5 words
    """
    lower = query.lower()
    allowed = _MODE_ALLOWED_CATEGORIES.get(si_drive_mode, {"safety", "tech", "fun"})
    best_score = 0
    best_response = None

    for keywords, response, category in PERSONA_RESPONSES:
        if category not in allowed:
            continue
        score = sum(len(kw) for kw in keywords if kw in lower)
        if score > best_score:
            best_score = score
            best_response = response

    if best_response is None or best_score == 0:
        return None

    # Cap all responses to 2 sentences max — long TTS kills latency
    sentences = re.split(r'(?<=[.!?])\s+', best_response)
    if len(sentences) > 2:
        best_response = " ".join(sentences[:2])

    # Truncate further based on mode
    if si_drive_mode == "Sport":
        # First sentence only
        for sep in (". ", "! ", "? ", " — "):
            idx = best_response.find(sep)
            if idx > 0:
                best_response = best_response[:idx + 1]
                break
    elif si_drive_mode == "Sport Sharp":
        # 5 words max
        words = best_response.split()[:5]
        best_response = " ".join(words)
        if not best_response.endswith("."):
            best_response += "."

    return best_response


class LLMEngine:
    """Local LLM engine using Ollama on Jetson.

    Usage:
        engine = LLMEngine()
        engine.start()
        response = engine.query("How are my brakes?", telemetry_context="...")
        engine.stop()

    Falls back to persona keyword matching when Ollama is unavailable.
    """

    def __init__(
        self,
        ollama_url: str = OLLAMA_URL,
        model: str = DEFAULT_MODEL,
        fallback_model: str = FALLBACK_MODEL,
    ) -> None:
        self._url = ollama_url
        self._model = model
        self._fallback_model = fallback_model
        self._running = False
        self._available_model: Optional[str] = None

    def start(self) -> None:
        """Check Ollama connectivity and find available model."""
        if self._running:
            return

        self._available_model = self._find_model()
        self._running = True

        if self._available_model:
            log.info("LLM engine ready: %s via Ollama", self._available_model)
        else:
            log.warning("Ollama not available — using persona keyword matching")

    def stop(self) -> None:
        self._running = False
        self._available_model = None
        log.info("LLM engine stopped")

    def _find_model(self) -> Optional[str]:
        """Check Ollama for available models."""
        try:
            req = urllib.request.Request(f"{self._url}/api/tags")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                models = [m["name"] for m in data.get("models", [])]

            # Prefer primary model, then fallback
            for candidate in [self._model, self._fallback_model]:
                # Check exact match or prefix match (ollama may append :latest)
                for m in models:
                    if m == candidate or m.startswith(candidate.split(":")[0]):
                        return m

            if models:
                log.info("Neither %s nor %s found. Available: %s", self._model, self._fallback_model, models)
                return models[0]  # Use whatever is available

            log.warning("No models found in Ollama")
            return None
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            log.debug("Ollama not reachable: %s", exc)
            return None

    def query(
        self,
        user_message: str,
        telemetry_context: str = "",
        memory_context: str = "",
        si_drive_mode: str = "Intelligent",
    ) -> LLMResponse:
        """Send a query to the LLM (or persona fallback).

        Args:
            user_message: What the driver said/asked.
            telemetry_context: Current telemetry snapshot as text.
            memory_context: Relevant memories from edge memory system.
            si_drive_mode: Current SI Drive mode name.

        Returns:
            LLMResponse with text and metadata.
        """
        start_time = time.monotonic()
        max_tokens = MODE_TOKEN_CAPS.get(si_drive_mode, 64)

        # Persona keyword matching FIRST — instant (<1ms) curated responses
        matched = _match_persona(user_message, si_drive_mode)
        if matched:
            latency = time.monotonic() - start_time
            return LLMResponse(
                text=matched,
                model="persona_keywords",
                tier="persona_match",
                latency_s=latency,
                tokens=len(matched.split()),
            )

        # Ollama for novel/complex questions (2-4s on Orin Nano)
        if self._available_model:
            try:
                return self._query_ollama(
                    user_message, telemetry_context, memory_context,
                    si_drive_mode, max_tokens, start_time,
                )
            except Exception as exc:
                log.warning("Ollama query failed: %s — using fallback", exc)

        # Final fallback
        latency = time.monotonic() - start_time
        return LLMResponse(
            text=FALLBACK_RESPONSE,
            model="fallback",
            tier="fallback",
            latency_s=latency,
            tokens=len(FALLBACK_RESPONSE.split()),
        )

    def _query_ollama(
        self,
        user_message: str,
        telemetry_context: str,
        memory_context: str,
        si_drive_mode: str,
        max_tokens: int,
        start_time: float,
    ) -> LLMResponse:
        """Query Ollama's OpenAI-compatible chat API."""
        system_prompt = KISTI_SYSTEM_PROMPT.format(
            telemetry_context=telemetry_context or "No live telemetry available.",
        )

        # Inject memory context (skip in Sport Sharp — every token counts)
        if memory_context and si_drive_mode != "Sport Sharp":
            system_prompt += f"\n\nRelevant memories:\n{memory_context}"

        # Mode-specific prompt reinforcement (kept minimal — prompt tokens cost time)
        if si_drive_mode == "Sport":
            system_prompt += "\n\nSPORT MODE: One sentence max. Numbers and status only."
        elif si_drive_mode == "Sport Sharp":
            system_prompt += "\n\nSPORT SHARP: Critical safety only. 5 words max. Silence otherwise."

        temperature = MODE_TEMPERATURE.get(si_drive_mode, 0.6)

        payload = {
            "model": self._available_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
                "stop": ["\n\n", "---"],
            },
        }

        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self._url}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())

        text = data.get("message", {}).get("content", "").strip()
        latency = time.monotonic() - start_time
        tokens = data.get("eval_count", len(text.split()))

        log.debug("LLM: '%s' → '%s' (%.1fs, %d tok)", user_message[:30], text[:50], latency, tokens)

        return LLMResponse(
            text=text,
            model=self._available_model or "unknown",
            tier="local_llm",
            latency_s=latency,
            tokens=tokens,
        )

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_real(self) -> bool:
        """True if connected to Ollama with a real model."""
        return self._available_model is not None
