"""KiSTI — Engine Build Record (IAG-14894)

Structured build specification for the IAG Performance 750 Closed Deck
Short Block. This is the data anchor for the entire KiSTI system —
deterministic baseline modeling starts here.

Installed: 2026-03-27 (pre-first start)
Body odometer at install: 113,736 km
Engine hours at install: 0
"""

from dataclasses import dataclass, field
from datetime import date

INSTALL_DATE = date(2026, 3, 27)
BODY_KM_AT_INSTALL = 113_736
ENGINE_KM_AT_INSTALL = 0


@dataclass(frozen=True)
class EngineSpec:
    """Immutable engine build specification."""
    engine_id: str = "IAG-14894"
    builder: str = "IAG Performance"
    serial: int = 14894
    platform: str = "Subaru EJ25 (EJ257-based)"
    config: str = "IAG 750 Closed Deck Forged Short Block"
    power_capability_bhp: int = 750
    current_tune_whp: str = "360-390"

    # Casting / machining traceability
    casting: str = "B25"
    batch_code: str = "F706"
    cast_stamp: str = "EJ25"
    machined_stamps: tuple = ("22222", "91 BB", "16 BB")

    # Bottom end
    head_studs: str = "ARP Custom Age"
    oil_pickup: str = "IAG Oil Pickup + Windage Tray"

    # Valvetrain
    intake_valves: str = "GSC 36mm"
    exhaust_valves: str = "GSC 32mm"
    valve_guides: str = "Bronze"
    springs: str = "Beehive + Titanium Retainers"

    # Induction
    intercooler: str = "COBB Front Mount"
    tgv_housings: str = "PrecisionWorks Billet"
    map_sensor: str = "4-Bar"

    # Fuel
    injectors: str = "ID1300"
    fuel_pump: str = "Deatschwerks DW300C"
    fuel_system: str = "IAG PTFE + FPR"

    # Turbo
    turbo: str = "BCP X400 (~400 WHP class)"

    # Cooling / support
    cyl4_cooling_mod: bool = True
    radiator: str = "CSF Aluminum"
    oil_pressure_sensor: str = "0-150 PSI"
    fuel_pressure_sensor: bool = True


ENGINE = EngineSpec()


def build_summary() -> str:
    """Concise build summary for LLM context injection."""
    return (
        f"Engine: {ENGINE.engine_id} — {ENGINE.config}, {ENGINE.power_capability_bhp} bhp capable. "
        f"Turbo: {ENGINE.turbo}. Fuel: {ENGINE.injectors}, {ENGINE.fuel_pump}. "
        f"Valves: {ENGINE.intake_valves} intake, {ENGINE.exhaust_valves} exhaust, {ENGINE.springs}. "
        f"Head studs: {ENGINE.head_studs}. Intercooler: {ENGINE.intercooler}. "
        f"Cyl 4 cooling mod: yes. Radiator: {ENGINE.radiator}. "
        f"Body: {BODY_KM_AT_INSTALL:,} km. Engine: 0 km (installed {INSTALL_DATE})."
    )


def build_detail() -> str:
    """Full build detail for persona responses."""
    return f"""IAG Performance 750 Closed Deck Forged Short Block, serial #{ENGINE.serial}.
EJ257-based, {ENGINE.power_capability_bhp} bhp hardware capability, currently tuned {ENGINE.current_tune_whp} WHP.

Bottom end: {ENGINE.config}, {ENGINE.head_studs} head studs, {ENGINE.oil_pickup}.
Valvetrain: {ENGINE.intake_valves} intake, {ENGINE.exhaust_valves} exhaust, {ENGINE.valve_guides} guides, {ENGINE.springs}.
Fuel: {ENGINE.injectors} injectors, {ENGINE.fuel_pump} pump, {ENGINE.fuel_system}.
Turbo: {ENGINE.turbo}.
Induction: {ENGINE.intercooler} FMIC, {ENGINE.tgv_housings} TGV housings, {ENGINE.map_sensor} MAP sensor.
Cooling: {ENGINE.radiator} radiator, Cylinder 4 cooling mod installed.

Casting marks: {ENGINE.casting}, batch {ENGINE.batch_code}, stamps {', '.join(ENGINE.machined_stamps)}.
Installed {INSTALL_DATE}. Body: {BODY_KM_AT_INSTALL:,} km. Engine: 0 km — fresh build, pre-first start."""
