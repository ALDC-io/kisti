# KiSTI Persona Response Gap Audit (2026-03-30)

**Current**: 57 responses (7 safety, 17 tech, 33 fun)
**Gaps identified**: ~42 keyword entries needed (~25-30 high-value responses)

## TIER 1: HIGH PRIORITY (12 responses)

### DCCD & AWD System Education (2 responses)
- `["dccd", "center diff", "biasing", "differential"]` → "The DCCD is a mechanical center differential with electronically controlled biasing. It reads wheel slip and adjusts torque between front and rear — rear-biased under hard acceleration, front-biased for cornering grip."
- `["feel dccd", "sense bias", "locking", "engagement"]` → "You feel it as increased rear grip in hard cornering and launch. It is smooth, continuous biasing — not a mechanical locker."

### Turbo Operation (4 responses)
- `["turbo spool", "spool time", "boost response"]` → "Full boost by 3,200 RPM on moderate load. The BCP X400 spools linear after that — no lag, just upward acceleration."
- `["turbo lag", "delay", "response"]` → "Brief moment between throttle and full boost — the compressor needs RPM. That pause then sudden acceleration is turbo lag."
- `["turbo whistle", "turbo sound", "turbo noise"]` → "High-pitched whistle is the compressor spinning. Deeper whine is boost being made. That is your turbo talking."
- `["turbo maintenance", "turbo service", "bearing"]` → "Oil circulation keeps the bearing alive. Inspect turbo inlet and outlet at every oil change. Cold spool before hard driving equals longer bearing life."

### Oil & Coolant Service (3 responses)
- `["oil change", "service", "schedule", "maintenance interval"]` → "Fresh engine: change every 5,000 km for the first 20,000. After that, 8,000 km intervals. Motul X-Clean 5W40 every time."
- `["coolant", "flush", "coolant service"]` → "Super Blue coolant every 20,000 km or 2 years. The Cyl 4 cooling mod depends on consistent coolant flow."
- `["oil pressure low", "pressure drop", "low psi"]` → "Under 25 PSI idle warm? Check oil level first. If topped up and still low, Killer B pickup may be clogged. Get it scanned."

### Fuel Economy & Range (3 responses)
- `["fuel economy", "consumption", "mpg", "km per liter"]` → "Highway: 7 to 9 km per liter. City: 5 to 6. Full boost sprints kill that. It is a 390 wheel horsepower car — economy is what it is."
- `["range", "miles to empty", "how far can we go"]` → "Roughly 360 to 540 km per tank depending on throttle discipline. Keep an eye on the fuel pressure gauge."
- `["fuel grade", "octane", "e85", "what fuel"]` → Already partially covered — enhance existing response.

## TIER 1: SAFETY (2 responses)

### Engine Knock Detection
- `["knock", "ping", "detonation", "pinging"]` → "Metallic pinging is engine knock. Switch to higher octane, back off boost, or let IAT cool down. Continue and you risk the block."
- `["fuel quality", "low octane", "cheap fuel"]` → "The IAG 750 demands 91 octane minimum. Cheap fuel plus full boost equals knock. Trust the pressure gauge and IAT reading."

## TIER 2: DRIVING TECHNIQUE (6 responses)

### Braking & Cornering
- `["braking", "brake technique", "threshold", "trail brake"]` → "Brake hard early, taper as you approach the turn. Trail braking shifts weight forward for turn-in grip."
- `["cornering", "apex", "turn", "line", "racing line"]` → "Smooth steering inputs. Apex late to carry speed out. The DCCD biases torque rearward in the corner — trust the grip."
- `["corner speed", "g-force", "lateral g"]` → "This car handles around 1.0 lateral g. Speed through a turn equals the square root of grip times radius. You will feel it."
- `["weight transfer", "load", "grip"]` → "Hard braking shifts weight forward. Hard acceleration shifts it back. DCCD uses that. Smooth transitions equals faster driving."

### Emergency Procedures
- `["overheat", "overtemp", "emergency", "shutdown"]` → "Coolant above 105? Back off immediately. Find safe place to stop. Engine off, let it cool. Do not open the radiator cap while hot."
- `["blowout", "tire failure", "flat"]` → "Sudden grip loss? Do not slam brakes. Ease off throttle, steer straight, gradually coast to safety. AWD grip will help you control it."

## TIER 3: COMPONENT SPECS (8 responses — lower priority)

- Clutch: `["clutch", "holding capacity"]` → Competition Clutch Stage 2
- Flywheel: `["flywheel", "weight reduction"]` → ACT Lightweight
- AiM Strada: `["aim", "dash", "telemetry display"]` → AiM Strada 7" Street
- Brakes: `["brake fluid", "dot4", "pentosin"]` → Pentosin DOT 4
- Exhaust: `["grimmspeed", "exhaust gasket"]` → Grimmspeed gasket set
- Suspension: `["suspension brand", "kyb", "strut"]` → KYB + Fortune Auto
- Swaybars: `["sway bar", "anti-roll"]` → GR front/rear swaybars
- PDM: `["pdm", "power distribution"]` → Link Razor PDM

## Implementation Notes

- All TIER 1 TECH → available in Intelligent + Sport modes
- All SAFETY → available in ALL modes including Sport Sharp
- TIER 3 FUN → Intelligent only
- Keep responses to 2 sentences max (TTS latency constraint)
- Use build_record.py values, not hardcoded numbers
