# KiSTI Voice Command Routing Analysis

## Overview
Thorough exploration of voice command dispatch, frontier engine lifecycle, and edge memory settings for adding "enable cloud" / "disable cloud" voice commands.

---

## 1. Voice Command Routing (`voice/voice_manager.py:605-660`)

### Command Dispatch Logic

**File**: `/home/aldc/repos/kisti/voice/voice_manager.py`
**Method**: `handle_voice_query()` (lines 608-704)
**Architecture**: Linear if-chain dispatch with early returns. Pattern: check-prefix → handle → return.

#### Command Tiers (in execution order):

```python
# Tier 1: "say" command (TTS latency test, skips LLM)
# Lines 616-623
if lower.startswith("say "):
    phrase = transcription[len("say "):].strip()
    if phrase:
        log.info("Say command: '%s'", phrase)
        resp = VoiceResponse(text=phrase, source="command", tier="system")
        self._compose_and_speak(resp, user_text=transcription, trace=trace)
        return
```

```python
# Tier 2: "remember" command (edge memory storage)
# Lines 625-638
if lower.startswith("remember ") and self._edge_memory:
    content = transcription[len("remember "):].strip()
    if content:
        self._edge_memory.remember(
            content=content,
            memory_type="manual",
            source="voice",
        )
        resp = VoiceResponse(
            text="Got it. I'll remember that.", source="command", tier="system",
        )
        self._compose_and_speak(resp, user_text=transcription, trace=trace)
        return
```

```python
# Tier 3: Quiet/Resume toggle (state machine)
# Lines 640-652
QUIET_COMMANDS = ["quiet please kisti", "quiet please", "quiet kisti", "be quiet"]
RESUME_COMMANDS = ["hey kisti"]

if any(cmd in lower for cmd in QUIET_COMMANDS):
    self._toggle_state = VoiceToggleState.QUIET
    self._set_state(VoiceState.QUIET)
    resp = VoiceResponse(text="Going quiet.", source="system", tier="system")
    self._compose_and_speak(resp, user_text=transcription)
    return

if any(cmd in lower for cmd in RESUME_COMMANDS) and self._state == VoiceState.QUIET:
    self._toggle_state = VoiceToggleState.NORMAL
    self._set_state(VoiceState.IDLE)
    resp = VoiceResponse(text="I'm back. What do you need?", source="system", tier="system")
    self._compose_and_speak(resp, user_text=transcription)
    return
```

```python
# Tier 4: Timing commands (e.g., "reset timing", "lap time")
# Lines 654-659
timing_cmd = self._handle_timing_command(lower)
if timing_cmd:
    resp = VoiceResponse(text=timing_cmd, source="command", tier="system")
    self._compose_and_speak(resp, user_text=transcription, trace=trace)
    return
```

```python
# Tier 5+: Persona/sensor/LLM routing
# Lines 661-704
# (Sets THINKING state, then routes through persona/timing/sensors → LLM)
```

### Key Constants
- **Lines 227-228**: Command keyword lists
  ```python
  QUIET_COMMANDS = ["quiet please kisti", "quiet please", "quiet kisti", "be quiet"]
  RESUME_COMMANDS = ["hey kisti"]
  ```

### Response Pattern
All system commands use:
```python
resp = VoiceResponse(text=response_text, source="command", tier="system")
self._compose_and_speak(resp, user_text=transcription, trace=trace)
```

---

## 2. Frontier Engine Lifecycle (`voice/frontier_engine.py`)

### FrontierLLMEngine Class
**File**: `/home/aldc/repos/kisti/voice/frontier_engine.py`
**Class**: `FrontierLLMEngine` (lines 63-413)

#### Lifecycle Methods

**`__init__()`** (lines 81-95)
Initialization — does NOT start the engine:
```python
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
```

**`start()`** (lines 99-127)
Launches WiFi checker daemon thread and initializes cache table:
```python
def start(self) -> None:
    """Start WiFi checker and initialize cache table."""
    if self._running:
        return

    # Initialize cache table if we have a DB connection
    if self._conn:
        try:
            self._conn.execute(FRONTIER_CACHE_DDL)
            log.info("Frontier cache table initialized")
        except Exception as exc:
            log.warning("Failed to create frontier_cache table: %s", exc)

    # Start WiFi checker thread
    if self._api_key:
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
    else:
        log.warning("No API key — frontier engine disabled")

    self._running = True
```

**`stop()`** (lines 129-136)
Halts WiFi checker thread:
```python
def stop(self) -> None:
    """Stop WiFi checker thread."""
    self._stop_wifi_check = True
    if self._wifi_check_thread:
        self._wifi_check_thread.join(timeout=5)
        self._wifi_check_thread = None
    self._running = False
    log.info("Frontier LLM engine stopped")
```

#### State Properties
- **`is_running`** (line 143-144): Returns `self._running`
- **`wifi_available`** (line 138-140): Returns `self._wifi_available` (set by WiFi checker)

#### Query Method
**`query()`** (lines 169-233)
Routing: cache → WiFi check → live API → None
```python
def query(
    self,
    user_message: str,
    telemetry_context: str = "",
    memory_context: str = "",
    si_drive_mode: str = "Intelligent",
) -> Optional[LLMResponse]:
    """Try cache then live API. Returns None if unavailable."""
    if not self._running or not self._api_key:
        return None

    # Tier 2: Check local cache first
    # Tier 3: Live API call (requires WiFi)
    # Returns None if offline and cache miss
```

#### Key Design Patterns
- **Thread-safe state**: `_running` and `_wifi_available` are atomically readable
- **No stop blocking**: `start()` checks `if self._running: return` (idempotent)
- **Graceful offline**: Returns `None` if `_running=False` — LLMEngine falls back

---

## 3. Edge Memory Schema (`data/edge_memory.py`)

### Memories Table DDL
**File**: `/home/aldc/repos/kisti/data/edge_memory.py`
**Lines**: 24-41

```sql
CREATE TABLE IF NOT EXISTS memories (
    memory_id TEXT PRIMARY KEY,
    session_id TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    memory_type TEXT,
    source TEXT,
    content TEXT NOT NULL,
    tags TEXT,
    importance DOUBLE DEFAULT 0.5,
    visibility TEXT DEFAULT 'private',
    embedding FLOAT[384],
    zeus_memory_id TEXT,
    zeus_version INTEGER DEFAULT 0,
    synced BOOLEAN DEFAULT FALSE,
    zeus_enriched BOOLEAN DEFAULT FALSE
);
```

### Key Observations
1. **NO settings table exists** — intentional design. Each memory is timestamped + immutable.
2. **Memory types** (line 50-57):
   - `manual` (0.8 importance)
   - `maintenance` (0.8 importance)
   - `alert_pattern` (0.6 importance)
   - `session_summary` (0.5 importance)
   - `driving_insight` (0.5 importance)
3. **Visibility levels** (line 44-48): `private`, `team`, `public`

### EdgeMemory Class Methods
- **`remember()`** (lines 102-139): Insert new memory
- **`get_memory(id)`** (lines 143-150): Retrieve by ID
- **`get_recent()`** (lines 152-169): Fetch recent memories
- **`search()`** (lines 172-187): Semantic or keyword search
- **`mark_synced()`** (lines 263-269): Mark as synced to Zeus
- **`apply_zeus_enrichment()`** (lines 271-297): Apply enrichments from Zeus

---

## 4. LLM Engine Frontier Wiring (`voice/llm_engine.py`)

### LLMEngine Class Initialization
**File**: `/home/aldc/repos/kisti/voice/llm_engine.py`
**Lines**: 529-541

```python
def __init__(
    self,
    ollama_url: str = OLLAMA_URL,
    model: str = DEFAULT_MODEL,
    fallback_model: str = FALLBACK_MODEL,
    frontier: object = None,  # Optional FrontierLLMEngine injected
) -> None:
    self._url = ollama_url
    self._model = model
    self._fallback_model = fallback_model
    self._running = False
    self._available_model: Optional[str] = None
    self._frontier = frontier  # Optional FrontierLLMEngine
```

### Query Tier Resolution
**`query()`** (lines 586-649)

**Resolution order**:
1. **Persona keyword matching** (lines 608-617): <1ms instant responses
2. **Ollama** (lines 621-628): CURRENTLY DISABLED (GPU memory reserved)
3. **Frontier** (lines 631-639): Claude API with cache fallback
4. **Fallback** (lines 642-649): Static response

**Frontier code path** (lines 631-639):
```python
# Frontier AI — cloud-connected Claude API with edge cache
if self._frontier:
    try:
        frontier_resp = self._frontier.query(
            user_message, telemetry_context, memory_context, si_drive_mode,
        )
        if frontier_resp is not None:
            return frontier_resp
    except Exception as exc:
        log.warning("Frontier query failed: %s — using fallback", exc)

# Final fallback
latency = time.monotonic() - start_time
return LLMResponse(
    text=FALLBACK_RESPONSE,
    model="fallback",
    tier="fallback",
    latency_s=latency,
    tokens=len(FALLBACK_RESPONSE.split()),
)
```

---

## 5. Frontier Integration in VoiceManager

### Initialization
**File**: `/home/aldc/repos/kisti/voice/voice_manager.py`
**Lines**: 273-276

```python
# Frontier AI — Claude API when WiFi available, edge cache when offline
anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
self._frontier = FrontierLLMEngine(api_key=anthropic_key) if anthropic_key else None
self._llm = LLMEngine(frontier=self._frontier)
```

### Lifecycle in `start()`
**Lines**: 332-338

```python
def start(self) -> None:
    """Initialize all voice subsystems and start the worker thread."""
    self._stt.start()
    self._tts.start()
    if self._frontier:
        self._frontier.start()  # Launches WiFi checker thread
    self._llm.start()
    self._running = True
```

**Key property**: VoiceManager holds reference to `self._frontier` for runtime control.

---

## 6. Current System Initialization (main.py)

### Frontier Status
**Observation**: Frontier engine is **NOT wired in main.py** yet.

**What happens**:
1. VoiceManager creates `FrontierLLMEngine` from `ANTHROPIC_API_KEY` env var (voice_manager.py:274-275)
2. VoiceManager injects it into LLMEngine during construction (voice_manager.py:276)
3. VoiceManager starts frontier on `start()` call (voice_manager.py:337)

**Missing**: No database connection passed to frontier engine → **frontier cache is disabled**
- Frontier will query API live if WiFi available
- No offline cache due to missing `db_conn` parameter

---

## Recommendations for "Enable Cloud" / "Disable Cloud" Commands

### Option 1: Runtime Toggle (Recommended)
**Implementation**: Add `enable_frontier()` / `disable_frontier()` methods to VoiceManager

**Mechanism**:
```python
def _handle_frontier_commands(self, lower: str) -> bool:
    """Handle frontier cloud toggle commands."""
    if "enable cloud" in lower or "turn on cloud" in lower:
        if self._frontier and not self._frontier.is_running:
            self._frontier.start()
            self._compose_and_speak(
                VoiceResponse(text="Cloud enabled.", source="command", tier="system"),
                user_text=lower
            )
            return True

    if "disable cloud" in lower or "turn off cloud" in lower:
        if self._frontier and self._frontier.is_running:
            self._frontier.stop()
            self._compose_and_speak(
                VoiceResponse(text="Cloud disabled.", source="command", tier="system"),
                user_text=lower
            )
            return True

    return False
```

**Insertion point**: In `handle_voice_query()` after timing commands (line ~660), before persona routing.

### Option 2: Settings Table in Edge Memory
**Schema addition**:
```sql
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP
);
```

**Usage**:
- `settings.key = "frontier_enabled"`, `value = "true"` / `"false"`
- Checked on every query in LLMEngine

**Trade-off**: More complex, but survives restarts (persistent across sessions).

### Option 3: Hybrid (Recommended for KiSTI)
1. Runtime toggle for immediate effect (Option 1)
2. Persist state to edge memory settings table
3. Load state on app startup

---

## File Paths & Line Numbers Summary

| Component | File | Key Lines | Purpose |
|-----------|------|-----------|---------|
| Command dispatch | `voice/voice_manager.py` | 608-704 | `handle_voice_query()` main dispatch |
| Command constants | `voice/voice_manager.py` | 227-228 | `QUIET_COMMANDS`, `RESUME_COMMANDS` |
| Frontier lifecycle | `voice/frontier_engine.py` | 99-136 | `start()`, `stop()` methods |
| Frontier query | `voice/frontier_engine.py` | 169-233 | `query()` main entry point |
| Frontier wiring | `voice/voice_manager.py` | 273-276 | Initialization in VoiceManager |
| Frontier lifecycle | `voice/voice_manager.py` | 336-337 | `start()` method call |
| LLM query tiers | `voice/llm_engine.py` | 586-649 | `query()` resolution order |
| Edge memory schema | `data/edge_memory.py` | 24-41 | `memories` table DDL |
| No settings table | `data/edge_memory.py` | 1-376 | **No existing settings storage** |

---

## Conclusion

**Frontier engine is ready for toggle commands:**
- ✅ Lifecycle methods exist (`start()`, `stop()`, `is_running`)
- ✅ VoiceManager holds reference for control
- ✅ Command routing pattern established (if-chain with early return)
- ✅ Edge memory schema flexible (can add settings table for persistence)
- ⚠️ Frontier cache not connected to DB yet (pass `db_conn` in main.py)

**Next steps** (for Task #3 — Add voice commands):
1. Add frontier toggle commands to `voice_manager.py:handle_voice_query()` (Option 1)
2. Optionally add settings table to `data/edge_memory.py` for persistence (Option 3)
3. Load frontier state from settings on startup (Option 3)
4. Pass `db_conn` to FrontierLLMEngine in main.py for cache support
