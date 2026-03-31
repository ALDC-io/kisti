"""KiSTI - Frontier LLM Engine (Cloud AI with Edge Cache)

Network-connected frontier AI integration layer. Routes complex queries
to Claude API when WiFi is available, caches responses locally in DuckDB
for offline replay.

Privacy-first design:
  - Persona keyword matches never reach this engine (handled upstream)
  - ECU sensor queries never reach this engine (blocked by ECU guard)
  - Only general knowledge queries that missed persona matching arrive here
  - Telemetry context is included for relevant answers but no PII is sent

Query resolution tier:
  persona (0ms) → frontier_cache (2ms) → live frontier (~500ms) → fallback

Modeled on HybridSTTEngine WiFi-aware pattern (stt_engine.py:332-486).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Optional

from voice.llm_engine import (
    KISTI_SYSTEM_PROMPT,
    MODE_TEMPERATURE,
    MODE_TOKEN_CAPS,
    LLMResponse,
)

log = logging.getLogger("kisti.voice.frontier")

CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-haiku-4-5-20251001"
ANTHROPIC_VERSION = "2023-06-01"

# DuckDB schema for frontier response cache
FRONTIER_CACHE_DDL = """
CREATE TABLE IF NOT EXISTS frontier_cache (
    query_hash TEXT PRIMARY KEY,
    query_text TEXT NOT NULL,
    response_text TEXT NOT NULL,
    model TEXT DEFAULT 'claude-haiku-4-5',
    created_at TIMESTAMP,
    hit_count INTEGER DEFAULT 0,
    last_hit_at TIMESTAMP,
    ttl_days INTEGER DEFAULT 30
);
"""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _truncate_sentences(text: str, max_sentences: int = 2) -> str:
    """Keep only the first N sentences for concise TTS output."""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    if len(sentences) <= max_sentences:
        return text.strip()
    return " ".join(sentences[:max_sentences])


def _strip_markdown(text: str) -> str:
    """Strip markdown formatting so TTS doesn't speak asterisks/hashes."""
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)   # **bold**
    text = re.sub(r'\*(.+?)\*', r'\1', text)         # *italic*
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)  # # headers
    text = re.sub(r'`(.+?)`', r'\1', text)           # `code`
    text = re.sub(r'^\s*[-*]\s+', '', text, flags=re.MULTILINE)  # - bullets
    text = re.sub(r'\n{2,}', '. ', text)              # double newlines → period
    text = re.sub(r'\n', ' ', text)                    # single newlines → space
    return text.strip()


class FrontierLLMEngine:
    """Cloud frontier AI with local DuckDB response cache.

    Privacy-first: only general knowledge queries go to cloud.
    Persona/sensor queries never leave the edge — they are handled
    upstream by _match_persona() and the ECU guard.

    Usage:
        engine = FrontierLLMEngine(api_key="sk-...", db_conn=conn)
        engine.start()
        response = engine.query("Why do boxer engines have unequal headers?", ...)
        engine.stop()
    """

    WIFI_CHECK_INTERVAL_S = 30.0
    API_TIMEOUT_S = 10.0
    CACHE_TTL_DAYS = 30

    def __init__(
        self,
        api_key: str,
        db_conn: object = None,
        model: str = DEFAULT_MODEL,
        api_url: str = CLAUDE_API_URL,
    ) -> None:
        self._api_key = api_key
        self._conn = db_conn
        self._model = model
        self._api_url = api_url
        self._running = False
        self._wifi_available = False
        self._wifi_check_thread: Optional[threading.Thread] = None
        self._stop_wifi_check = False

    # ---- Lifecycle ----

    def start(self) -> None:
        """Start WiFi checker and initialize cache table."""
        if self._running:
            return

        # Cannot start without API key
        if not self._api_key:
            log.warning("No API key — frontier engine disabled")
            return

        # Initialize cache table if we have a DB connection
        if self._conn:
            try:
                self._conn.execute(FRONTIER_CACHE_DDL)
                log.info("Frontier cache table initialized")
            except Exception as exc:
                log.warning("Failed to create frontier_cache table: %s", exc)

        # Start WiFi checker thread
        self._stop_wifi_check = False
        self._wifi_check_thread = threading.Thread(
            target=self._wifi_checker, daemon=True
        )
        self._wifi_check_thread.start()
        log.info(
            "Frontier LLM engine started (model=%s, WiFi check every %.0fs)",
            self._model,
            self.WIFI_CHECK_INTERVAL_S,
        )
        self._running = True

    def stop(self) -> None:
        """Stop WiFi checker thread."""
        self._stop_wifi_check = True
        if self._wifi_check_thread:
            self._wifi_check_thread.join(timeout=5)
            self._wifi_check_thread = None
        self._running = False
        log.info("Frontier LLM engine stopped")

    @property
    def wifi_available(self) -> bool:
        return self._wifi_available

    @property
    def is_running(self) -> bool:
        return self._running

    # ---- WiFi Checker (HybridSTTEngine pattern) ----

    def _check_wifi(self) -> bool:
        """Check network connectivity with 2s timeout."""
        try:
            req = urllib.request.Request("https://www.google.com", method="HEAD")
            urllib.request.urlopen(req, timeout=2)
            return True
        except Exception:
            return False

    def _wifi_checker(self) -> None:
        """Background daemon thread: check WiFi every 30s."""
        while not self._stop_wifi_check:
            self._wifi_available = self._check_wifi()
            log.debug(
                "WiFi check: %s",
                "available" if self._wifi_available else "unavailable",
            )
            time.sleep(self.WIFI_CHECK_INTERVAL_S)

    # ---- Query ----

    def query(
        self,
        user_message: str,
        telemetry_context: str = "",
        memory_context: str = "",
        si_drive_mode: str = "Intelligent",
    ) -> Optional[LLMResponse]:
        """Try cache then live API. Returns None if unavailable.

        Args:
            user_message: The user's question (already past persona matching).
            telemetry_context: Current sensor snapshot.
            memory_context: Relevant edge memories.
            si_drive_mode: Current driving mode.

        Returns:
            LLMResponse if cache hit or API success, None otherwise.
        """
        if not self._running or not self._api_key:
            return None

        start_time = time.monotonic()
        query_hash = self._hash_query(user_message)

        # Tier 2: Check local cache first
        cached = self._check_cache(query_hash)
        if cached is not None:
            cached = _truncate_sentences(cached, max_sentences=2)
            latency = time.monotonic() - start_time
            log.info("Frontier cache hit: %s (%.1fms)", query_hash[:8], latency * 1000)
            return LLMResponse(
                text=cached,
                model=f"{self._model}/cached",
                tier="frontier_cache",
                latency_s=latency,
                tokens=len(cached.split()),
            )

        # Tier 3: Live API call (requires WiFi)
        if not self._wifi_available:
            log.debug("Frontier: offline, no cache hit for %s", query_hash[:8])
            return None

        response_text = self._call_api(
            user_message, telemetry_context, memory_context, si_drive_mode
        )
        if response_text is None:
            return None

        # Truncate to 2 sentences before caching and speaking
        response_text = _truncate_sentences(response_text, max_sentences=2)

        # Cache the response for offline replay
        self._cache_response(query_hash, user_message, response_text, self._model)

        latency = time.monotonic() - start_time
        log.info(
            "Frontier API response: %s (%.1fms, %d tokens)",
            query_hash[:8],
            latency * 1000,
            len(response_text.split()),
        )
        return LLMResponse(
            text=response_text,
            model=self._model,
            tier="frontier_live",
            latency_s=latency,
            tokens=len(response_text.split()),
        )

    # ---- Cache ----

    def _hash_query(self, query: str) -> str:
        """SHA-256 of normalized query for cache key."""
        normalized = query.lower().strip()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _check_cache(self, query_hash: str) -> Optional[str]:
        """Look up cached frontier response by query hash."""
        if not self._conn:
            return None

        try:
            rows = self._conn.execute(
                "SELECT response_text, created_at, ttl_days FROM frontier_cache "
                "WHERE query_hash = ?",
                [query_hash],
            ).fetchall()
        except Exception:
            return None

        if not rows:
            return None

        response_text, created_at, ttl_days = rows[0]

        # Check TTL expiry (DuckDB may return naive timestamps)
        if created_at and ttl_days:
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            expiry = created_at + timedelta(days=ttl_days)
            if _now() > expiry:
                # Expired — delete and miss
                try:
                    self._conn.execute(
                        "DELETE FROM frontier_cache WHERE query_hash = ?",
                        [query_hash],
                    )
                except Exception:
                    pass
                return None

        # Update hit count
        try:
            self._conn.execute(
                "UPDATE frontier_cache SET hit_count = hit_count + 1, "
                "last_hit_at = ? WHERE query_hash = ?",
                [_now(), query_hash],
            )
        except Exception:
            pass

        return response_text

    def _cache_response(
        self,
        query_hash: str,
        query_text: str,
        response_text: str,
        model: str,
    ) -> None:
        """Store frontier response in DuckDB cache."""
        if not self._conn:
            return

        try:
            self._conn.execute(
                "INSERT INTO frontier_cache "
                "(query_hash, query_text, response_text, model, "
                "created_at, hit_count, last_hit_at, ttl_days) "
                "VALUES (?, ?, ?, ?, ?, 0, NULL, ?) "
                "ON CONFLICT (query_hash) DO UPDATE SET "
                "response_text = EXCLUDED.response_text, "
                "model = EXCLUDED.model, "
                "created_at = EXCLUDED.created_at, "
                "hit_count = 0",
                [
                    query_hash,
                    query_text,
                    response_text,
                    model,
                    _now(),
                    self.CACHE_TTL_DAYS,
                ],
            )
        except Exception as exc:
            log.warning("Failed to cache frontier response: %s", exc)

    def cache_stats(self) -> dict:
        """Return cache statistics."""
        if not self._conn:
            return {"total": 0, "total_hits": 0}

        try:
            total = self._conn.execute(
                "SELECT COUNT(*) FROM frontier_cache"
            ).fetchone()[0]
            total_hits = self._conn.execute(
                "SELECT COALESCE(SUM(hit_count), 0) FROM frontier_cache"
            ).fetchone()[0]
            return {"total": total, "total_hits": total_hits}
        except Exception:
            return {"total": 0, "total_hits": 0}

    # ---- API Call ----

    def _call_api(
        self,
        user_message: str,
        telemetry_context: str,
        memory_context: str,
        si_drive_mode: str,
    ) -> Optional[str]:
        """POST to Claude Messages API. Returns response text or None."""
        # Give Claude enough room to finish 2 sentences cleanly.
        # System prompt enforces 1-2 sentences; _truncate_sentences is the backstop.
        _FRONTIER_TOKEN_CAPS = {"Intelligent": 120, "Sport": 60, "Sport Sharp": 20}
        max_tokens = _FRONTIER_TOKEN_CAPS.get(si_drive_mode, 60)
        temperature = MODE_TEMPERATURE.get(si_drive_mode, 0.6)

        # Build system prompt (same as Ollama path)
        system_prompt = KISTI_SYSTEM_PROMPT.format(
            telemetry_context=telemetry_context or "No live telemetry available.",
        )

        if memory_context and si_drive_mode != "Sport Sharp":
            system_prompt += f"\n\nRelevant memories:\n{memory_context}"

        system_prompt += "\n\nIMPORTANT: You are a voice co-driver. Keep answers to 1-2 short sentences max. Be punchy and direct — the driver is focused on the road. Never use markdown formatting (no **, *, #, `, or bullet points). Plain text only — output is read aloud by text-to-speech."

        if si_drive_mode == "Sport":
            system_prompt += "\n\nSPORT MODE: One sentence max. Numbers and status only."
        elif si_drive_mode == "Sport Sharp":
            system_prompt += "\n\nSPORT SHARP: Critical safety only. 5 words max. Silence otherwise."

        payload = {
            "model": self._model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_message},
            ],
        }

        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self._api_url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-api-key": self._api_key,
                "anthropic-version": ANTHROPIC_VERSION,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.API_TIMEOUT_S) as resp:
                data = json.loads(resp.read())

            # Extract text from Claude Messages API response
            content_blocks = data.get("content", [])
            text_parts = [
                b["text"] for b in content_blocks if b.get("type") == "text"
            ]
            text = " ".join(text_parts).strip()

            if not text:
                log.warning("Frontier API returned empty response")
                return None

            return _strip_markdown(text)

        except urllib.error.HTTPError as exc:
            log.warning("Frontier API HTTP error %d: %s", exc.code, exc.reason)
            return None
        except (urllib.error.URLError, OSError) as exc:
            log.warning("Frontier API network error: %s", exc)
            return None
        except (json.JSONDecodeError, KeyError) as exc:
            log.warning("Frontier API response parse error: %s", exc)
            return None
