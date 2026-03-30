# KiSTI Sensor Onboarding Guide

When a new sensor is added to the car, follow this checklist to make it fully queryable by voice.

## Onboarding Checklist

### 1. CAN Frame Definition (`can/can_config.py`)
- [ ] Add frame ID constant (e.g. `FRAME_NEW_SENSOR = 0x6XX`)
- [ ] Document byte layout, scaling factors, units
- [ ] Add to `ALL_FRAME_IDS` set

### 2. Decode/Encode Functions (`can/kisti_can.py`)
- [ ] Add `decode_new_sensor(data: bytes) -> dict`
- [ ] Add `encode_new_sensor(**kwargs) -> bytes` (for mock/test)
- [ ] Handle endianness, signed values, scaling

### 3. DiffState Fields (`model/vehicle_state.py`)
- [ ] Add field(s) to `DiffState` dataclass with defaults
- [ ] Add frame timestamp field (e.g. `new_sensor_ts: float = 0.0`)
- [ ] Add staleness check method if needed

### 4. Bridge Wiring (`model/vehicle_state.py` — DiffStateBridge)
- [ ] Add `update_new_sensor()` method to DiffStateBridge
- [ ] Set `can_connected = True` on update
- [ ] Emit `state_changed` signal

### 5. CAN Listener (`can/can_listener.py`)
- [ ] Add frame ID to dispatch table
- [ ] Route decoded data to `bridge.update_new_sensor()`

### 6. Voice Handler (`voice/voice_manager.py` — `_answer_from_sensors`)
- [ ] Add keyword matching block under `if s.can_connected:` (or `if s.ambient_available:` for USB sensors)
- [ ] Return human-spoken response with value + status interpretation
- [ ] Keep to 2 sentences max (TTS latency constraint)
- [ ] Include "not reading yet" fallback for zero/null values

### 7. Persona Fallback (`voice/llm_engine.py` — `PERSONA_RESPONSES`)
- [ ] Add keyword entry for when CAN is disconnected (general knowledge response)
- [ ] Set category: "tech" for specs, "safety" for critical, "fun" for trivia

### 8. Telemetry Context (`voice/voice_manager.py` — `_build_telemetry_context`)
- [ ] Add field to LLM context string so Ollama can reference it

### 9. Tests
- [ ] CAN decode/encode roundtrip test
- [ ] DiffStateBridge update test
- [ ] Voice handler test (mock DiffState with `can_connected=True`)
- [ ] Persona fallback test

### 10. Mock Generator (`can/mock_can_generator.py`)
- [ ] Add realistic simulated values for the new sensor
- [ ] Wire into mock CAN frame emission loop

## Sensor Sources

| Source | Connection | Gate Field |
|--------|-----------|------------|
| Link G5 Neo 4 ECU | CAN bus | `s.can_connected` |
| AiM GPS09 Pro | CAN bus | `s.can_connected` |
| Yoctopuce Meteo-V2 | USB | `s.ambient_available` |
| OEM (wheel speed, steering) | CAN via ECU | `s.can_connected` |
| Computed (timing, warmup) | Internal | Always available |

## Current Coverage (kisti-11)

- **93 total data elements** across all sensors
- **~50 voice-queryable** (ambient 6, ECU 25+, timing 15, persona ~28)
- **Key gaps**: GPS altitude/heading, IMU accel/gyro (pending GPS09 Pro install)
