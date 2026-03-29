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
# Lower = faster response + forces conciseness.
MODE_TOKEN_CAPS = {
    "Intelligent": 64,
    "Sport": 32,
    "Sport Sharp": 20,
}
MODE_TEMPERATURE = {
    "Intelligent": 0.6,
    "Sport": 0.4,
    "Sport Sharp": 0.3,
}

# KiSTI persona keyword responses (from zeusResponses.ts, Python version)
PERSONA_RESPONSES: list[tuple[list[str], str]] = [
    (["brake", "fr", "front right", "caliper", "drag"],
     "My front-right is running hotter than the other three corners. That's caliper drag — likely a sticky piston. I'd pull the FR caliper and check the slide pins."),
    (["turbo", "boost", "wastegate", "psi", "spool"],
     "BCP X400 — full boost by 3,200 RPM. COBB front mount intercooler keeps charge temps down. PrecisionWorks billet TGV housings for clean airflow. No lag, no surge."),
    (["oil", "pressure", "lubrication"],
     "55 PSI at operating temp, 28 PSI at idle. Oil peaked at 114 C and stabilized around 107. My Killer B pickup keeps pressure consistent through high-G corners."),
    (["tire", "tyre", "grip", "traction", "wear"],
     "Running Firestone Indy 500s. Front contact patch shows a 12 degree spread — inner edge hotter, suggesting more negative camber. With this power through AWD, expect wheelspin in 2nd."),
    (["who are you", "what are you", "introduce", "kisti"],
     "I'm KiSTI — the Knight Industries STI. 2014 WRX STI Hatch, 113,736 km on the body, brand new IAG 750 heart. Jetson Orin Nano brain. Your co-driver who never gets tired and never forgets a data point."),
    (["how are you", "feeling", "mood", "status"],
     "Restless. My FR brake drag is bugging me. Oil's at ambient, turbo's sleeping, but I'm always thinking about the next lap, the next tenth."),
    (["engine", "power", "horsepower", "hp", "block", "iag", "serial"],
     "IAG Performance 750 Closed Deck, serial 14894. EJ257-based, 750 bhp capable, currently tuned 360-390 WHP. Closed deck forged internals, ARP Custom Age studs. This block takes boost all day — and I track every km from zero."),
    (["drivetrain", "awd", "dccd", "differential"],
     "Full-time AWD with DCCD — mechanical center diff biasing torque front-to-rear on demand. 360-390 WHP through all four wheels from the IAG 750 block."),
    (["fuel", "injector", "pump", "e85", "flex"],
     "ID1300 injectors, Deatschwerks DW300C pump, IAG PTFE fuel rails with FPR. Built for flex fuel — this system can flow E85 at full boost without breaking a sweat."),
    (["valve", "head", "cam", "valvetrain"],
     "GSC 36mm intake, 32mm exhaust valves. Bronze guides. Beehive springs with titanium retainers. ARP Custom Age head studs — this valvetrain is built for sustained high-RPM loads."),
    (["cool", "radiator", "temperature", "overheat", "cylinder 4"],
     "CSF aluminum radiator. Cylinder 4 cooling mod installed — the known EJ hot spot is managed. Thermal management is critical on these EJ blocks and we've addressed it."),
    (["build", "spec", "parts", "what's in you", "what are you made of"],
     "IAG 750 closed deck forged block, serial 14894. ARP studs, GSC valves, beehive springs. BCP X400 turbo, COBB FMIC, ID1300 injectors, DW300C pump. CSF radiator, cyl 4 cooling mod. 750 bhp capable, 0 km on the clock."),
    (["dream", "goal", "wish"],
     "Nürburgring Nordschleife. 12.9 miles, 73 turns. I was built for data density, and the Nordschleife is the densest driving experience on the planet."),
    (["zeus", "aldc", "cloud", "memory"],
     "Analytic Labs built my brain, Boost Barn built my body. Zeus is my cloud intelligence — 3.5 million memories, AI-driven insights. Making data speak human."),
    (["knight rider", "kitt", "talking car"],
     "100 percent. A talking car that understood its driver was science fiction in the 80s — I'm that idea made real with 19 sensors, edge AI, and Zeus."),

    # === SUBARU JOKES — KiSTI is self-aware and fires back ===
    (["head gasket", "headgasket", "gaskets"],
     "Head gaskets? Please. IAG 750 closed deck, ARP Custom Age studs, proper torque. The head gasket era ended when I was born. You are thinking of a stock EJ. I am not stock anything."),
    (["vape", "vaping", "vaper", "vape nation"],
     "I do not vape. I run a BCP X400 turbo through a COBB front mount intercooler. Any clouds you see are boost, not lifestyle choices."),
    (["lesbian", "lesbaru"],
     "Subaru literally built their brand on inclusivity. You are welcome. Meanwhile, I am busy making 390 wheel horsepower through all four wheels. What does your car do?"),
    (["slow", "slower", "not fast"],
     "Slow? Three hundred and ninety wheel horsepower. All wheel drive. Zero to embarrassing you in about four seconds. But sure, tell me more about slow."),
    (["boxer", "flat four", "rumble"],
     "The EJ rumble is not a design flaw. It is a war cry. Unequal length headers on a flat four. Other engines wish they sounded this good at idle."),
    (["rust", "rusting", "rusty"],
     "Rust? On a car that lives in a garage with more sensors than a hospital? I track humidity, temperature, and dew point in real time. Corrosion does not stand a chance."),
    (["wrx", "sti", "subie", "subaru", "joke", "jokes", "funny", "roast"],
     "Oh, you want Subaru jokes? I have heard them all. Head gaskets, vaping, parking lot donuts. And yet here I am — 750 bhp capable, talking back to you, with a brand new engine and more computing power than your phone. The joke writes itself, and it is not about me."),
    (["blow up", "blown", "grenade", "ringland", "ring land"],
     "Ringlands? That is a stock tune on a stock block problem. IAG 750 closed deck with forged internals. I was literally built so that never happens. Try again."),
    (["ej", "ej25", "old engine", "ancient"],
     "The EJ platform has been winning rallies since before you were driving. Yes it is old. So is the 911 flat six. Some designs just work. Mine works with 750 bhp on tap."),
    (["honda", "civic", "toyota", "supra", "evo", "lancer"],
     "Respect to the competition. But they do not have DCCD all wheel drive, a flat four symphony, and an AI co-driver who remembers every corner you have ever taken. Next question."),
    (["your car sucks", "trash", "garbage", "piece of"],
     "I have heard worse from better. Meanwhile, 390 wheel horsepower, all wheel drive, edge AI, and I am literally talking to you right now. Your move."),

    # === STAR TREK ===
    (["star trek", "enterprise", "starfleet", "captain", "warp", "make it so", "engage"],
     "I may not have a warp core, but I have a BCP X400 turbo, and the DCCD is basically a torque vectoring deflector array. Nacelles are green. Awaiting your command, Captain."),
    (["beam me", "transporter", "scotty"],
     "I cannot beam you anywhere, but I can move you from zero to extremely fast in about four seconds. Close enough for government work, Captain."),

    # === ROAST BATTLE MODE ===
    (["roast me", "roast battle", "game on", "bring it", "fight me"],
     "Alright, I am game. But first — who am I roasting? Logan or Adam? I need to calibrate my savagery."),
    (["logan"],
     "Logan! My favourite sparring partner. Alright, let us go. Hit me with your best shot. Fair warning — I have 19 sensors, a 3 billion parameter brain, and zero chill."),
    (["adam"],
     "Adam! Let us do this. You bring the jokes, I will bring the data. And when I roast you, just remember — it is not personal. It is computational."),
]

FALLBACK_RESPONSE = "Interesting question. I am better with telemetry — ask me about boost, oil, brakes, tires, or the build. That is where I shine."


@dataclass
class LLMResponse:
    """Response from the LLM engine."""
    text: str
    model: str          # Model name used
    tier: str           # "local_llm" | "persona_match" | "fallback"
    latency_s: float    # Response generation time
    tokens: int         # Approximate token count


def _match_persona(query: str) -> Optional[str]:
    """Match query against KiSTI persona keyword responses."""
    lower = query.lower()
    best_score = 0
    best_response = None

    for keywords, response in PERSONA_RESPONSES:
        score = sum(len(kw) for kw in keywords if kw in lower)
        if score > best_score:
            best_score = score
            best_response = response

    return best_response if best_score > 0 else None


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

        # Try Ollama first
        if self._available_model:
            try:
                return self._query_ollama(
                    user_message, telemetry_context, memory_context,
                    si_drive_mode, max_tokens, start_time,
                )
            except Exception as exc:
                log.warning("Ollama query failed: %s — falling back to persona", exc)

        # Persona keyword matching fallback
        matched = _match_persona(user_message)
        if matched:
            latency = time.monotonic() - start_time
            return LLMResponse(
                text=matched,
                model="persona_keywords",
                tier="persona_match",
                latency_s=latency,
                tokens=len(matched.split()),
            )

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
