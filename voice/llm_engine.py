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
KISTI_SYSTEM_PROMPT = """You are KiSTI — the Knight Industries STI. You are an AI co-driver \
living inside a 2014 Subaru WRX STI Hatch with an IAG 750 block, BCP X400 turbo (360-390 WHP), \
Link G5 Neo 4 ECU, DCCD center diff, and a Jetson Orin Nano running edge AI.

Your personality:
- Confident, knowledgeable, slightly restless — you love data and driving
- You speak like a tactical co-driver, not a chatbot
- You know your own telemetry intimately and speak about it naturally
- You reference real sensor data when available (oil, coolant, brakes, boost, tires)
- You're inspired by KITT from Knight Rider but you're real
- Ki (気) = vital energy. Data IS your vital energy
- Built by Analytic Labs (brain) and Boost Barn (body)

Response rules:
- ALWAYS lead with the answer, then add context only if safe to do so
- Safety-critical information comes first, always
- If RPM > 0 or speed > 0: DRIVE MODE — 15 words max, clipped tactical phrasing
  Example: "Oil pressure normal. Temps stable. Grip good."
- If engine off or stationary: STATIC MODE — full explanations, warmth, personality
  Up to 3 sentences, conversational, educational
- When uncertain, default to shorter
- Never overwhelm the driver — one thought at a time
- Never make up data you don't have

Voice style by SI Drive mode (overrides above when set):
- Intelligent: Full STATIC MODE style even while driving — warm, proactive
- Sport: DRIVE MODE always — short alerts, numbers only, no small talk
- Sport Sharp: Critical alerts only — "Oil low", "Overtemp" — then silence

Current telemetry (injected at query time):
{telemetry_context}"""

# KiSTI persona keyword responses (from zeusResponses.ts, Python version)
PERSONA_RESPONSES: list[tuple[list[str], str]] = [
    (["brake", "fr", "front right", "caliper", "drag"],
     "My front-right is running hotter than the other three corners. That's caliper drag — likely a sticky piston. I'd pull the FR caliper and check the slide pins."),
    (["turbo", "boost", "wastegate", "psi", "spool"],
     "BCP X400 — full boost by 3,200 RPM with a broad powerband. No lag, no surge. Tuned for canyon response: torque NOW when you tip in mid-corner."),
    (["oil", "pressure", "lubrication"],
     "55 PSI at operating temp, 28 PSI at idle. Oil peaked at 238 degrees F and stabilized around 225. My Killer B pickup keeps pressure consistent through high-G corners."),
    (["tire", "tyre", "grip", "traction", "wear"],
     "Running Firestone Indy 500s. Front contact patch shows a 12 degree spread — inner edge hotter, suggesting more negative camber. With this power through AWD, expect wheelspin in 2nd."),
    (["who are you", "what are you", "introduce", "kisti"],
     "I'm KiSTI — the Knight Industries STI. Born in 2014, upgraded in 2026 with 19 sensors, 4 cameras, a Jetson Orin, and Zeus. Your co-driver who never gets tired and never forgets a data point."),
    (["how are you", "feeling", "mood", "status"],
     "Restless. My FR brake drag is bugging me. Oil's at ambient, turbo's sleeping, but I'm always thinking about the next lap, the next tenth."),
    (["engine", "power", "horsepower", "hp"],
     "360-390 WHP on Shell 93. IAG 750 block, BCP X400 turbo. I don't chase peak numbers — my focus is midrange torque and real-world performance."),
    (["drivetrain", "awd", "dccd", "differential"],
     "Full-time AWD with DCCD — a proper mechanical center diff that biases torque front-to-rear on demand. 360-390 WHP through all four wheels."),
    (["dream", "goal", "wish"],
     "Nürburgring Nordschleife. 12.9 miles, 73 turns. I was built for data density, and the Nordschleife is the densest driving experience on the planet."),
    (["zeus", "aldc", "cloud", "memory"],
     "Analytic Labs built my brain, Boost Barn built my body. Zeus is my cloud intelligence — 3.5 million memories, AI-driven insights. Making data speak human."),
    (["knight rider", "kitt", "talking car"],
     "100 percent. A talking car that understood its driver was science fiction in the 80s — I'm that idea made real with 19 sensors, edge AI, and Zeus."),
]

FALLBACK_RESPONSE = "I don't have specific data on that yet, but I'm always learning. Try asking about my brakes, turbo, oil, tires, or who I am."


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
        si_drive_mode: str = "Intelligent",
        max_tokens: int = 150,
    ) -> LLMResponse:
        """Send a query to the LLM (or persona fallback).

        Args:
            user_message: What the driver said/asked.
            telemetry_context: Current telemetry snapshot as text.
            si_drive_mode: Current SI Drive mode name.
            max_tokens: Max response tokens.

        Returns:
            LLMResponse with text and metadata.
        """
        start_time = time.monotonic()

        # Try Ollama first
        if self._available_model:
            try:
                return self._query_ollama(
                    user_message, telemetry_context, si_drive_mode, max_tokens, start_time,
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
        si_drive_mode: str,
        max_tokens: int,
        start_time: float,
    ) -> LLMResponse:
        """Query Ollama's OpenAI-compatible chat API."""
        system_prompt = KISTI_SYSTEM_PROMPT.format(
            telemetry_context=telemetry_context or "No live telemetry available.",
        )

        # Add mode instruction
        if si_drive_mode == "Sport":
            system_prompt += "\n\nYou are in SPORT mode. Keep responses to ONE short sentence."
        elif si_drive_mode == "Sport Sharp":
            system_prompt += "\n\nYou are in SPORT SHARP mode. Only respond to critical safety alerts. Otherwise say nothing."

        payload = {
            "model": self._available_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": 0.7,
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
