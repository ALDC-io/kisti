"""KiSTI — Engine Build Record (IAG-14894)

Structured build specification for the IAG Performance 750 Closed Deck
Short Block. This is the data anchor for the entire KiSTI system —
deterministic baseline modeling starts here.

Source: Boost Barn Motorsports Work Order #15562
Vehicle: 2014 Subaru WRX STI (JF1GR8H62EL215094)
Installed: 2026-03-27 (pre-first start)
Body odometer at install: 113,736 km
Engine hours at install: 0
"""

from dataclasses import dataclass
from datetime import date

INSTALL_DATE = date(2026, 3, 27)
BODY_KM_AT_INSTALL = 113_736
ENGINE_KM_AT_INSTALL = 0
VIN = "JF1GR8H62EL215094"
WORK_ORDER = "Boost Barn #15562"


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

    # Vehicle
    vin: str = VIN
    work_order: str = WORK_ORDER

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
    valve_seals: str = "Viton"

    # Induction
    intercooler: str = "COBB Front Mount"
    tgv_housings: str = "PrecisionWorks Billet"
    turbo_inlet: str = "Perrin Turbo Inlet Hose"
    map_sensor: str = "4-Bar"
    iat_sensor: str = "GM IAT (relocated to FMIC)"

    # Fuel
    injectors: str = "ID1300"
    fuel_pump: str = "Deatschwerks DW300C"
    fuel_rails: str = "IAG PTFE"
    fuel_regulator: str = "Aeromotive FPR"
    flex_fuel_sensor: bool = True

    # Turbo
    turbo: str = "BCP X400 (~400 WHP class)"

    # Cooling / reliability
    cyl4_cooling_mod: bool = True
    radiator: str = "CSF Aluminum"
    oil_separator: str = "IAG AOS"
    timing_service: str = "Belt, water pump, thermostat"
    gasket_refresh: bool = True

    # Sensors (KiSTI critical)
    oil_pressure_sensor: str = "0-150 PSI"
    fuel_pressure_sensor: str = "0-100 PSI"

    # Electronics
    ecu: str = "Link G5 Neo 4"
    pdm: str = "Link Razor PDM"
    keypad: str = "Link CAN Keypad (8 button)"
    dash: str = "AiM Strada 7\" Street Edition"


ENGINE = EngineSpec()


# ========================================================================
# Baseline alert thresholds — initial targets from engineering profile.
# These are starting points; KiSTI should learn actual baselines from
# real telemetry data over the first few sessions.
# ========================================================================

@dataclass(frozen=True)
class BaselineTargets:
    """Expected operating ranges for a fresh IAG 750 build."""

    # Oil pressure (PSI)
    oil_idle_warm_low: float = 15.0
    oil_idle_warm_high: float = 25.0
    oil_per_1000_rpm: float = 10.0   # rule of thumb
    oil_high_rpm_low: float = 70.0
    oil_high_rpm_high: float = 90.0

    # Coolant (Celsius)
    coolant_normal_low: float = 85.0
    coolant_normal_high: float = 95.0
    coolant_alert: float = 105.0

    # IAT post-FMIC (Celsius above ambient)
    iat_above_ambient_normal: float = 25.0
    iat_heat_soak_alert: float = 50.0

    # Fuel pressure (PSI)
    fuel_base_psi: float = 43.5      # 3 bar
    fuel_boost_ratio: float = 1.0    # rises 1:1 with boost

    # AFR targets
    afr_cruise: float = 14.7         # gasoline stoich
    afr_boost_gas_low: float = 11.0
    afr_boost_gas_high: float = 11.8
    # E85 runs richer — separate targets when flex fuel active


BASELINES = BaselineTargets()


def build_summary() -> str:
    """Concise build summary for LLM context injection."""
    return (
        f"Engine: {ENGINE.engine_id} — {ENGINE.config}, {ENGINE.power_capability_bhp} bhp capable. "
        f"VIN: {ENGINE.vin}. Work order: {ENGINE.work_order}. "
        f"Turbo: {ENGINE.turbo}. Fuel: {ENGINE.injectors}, {ENGINE.fuel_pump}, {ENGINE.fuel_regulator}. "
        f"Valves: {ENGINE.intake_valves} intake, {ENGINE.exhaust_valves} exhaust, {ENGINE.springs}. "
        f"Head studs: {ENGINE.head_studs}. FMIC: {ENGINE.intercooler}. AOS: {ENGINE.oil_separator}. "
        f"Cyl 4 cooling mod. Radiator: {ENGINE.radiator}. "
        f"ECU: {ENGINE.ecu}. Dash: {ENGINE.dash}. "
        f"Body: {BODY_KM_AT_INSTALL:,} km. Engine: 0 km (installed {INSTALL_DATE})."
    )


def build_detail() -> str:
    """Full build detail for persona responses."""
    return f"""IAG Performance 750 Closed Deck Forged Short Block, serial #{ENGINE.serial}.
EJ257-based, {ENGINE.power_capability_bhp} bhp hardware capability, currently tuned {ENGINE.current_tune_whp} WHP.
VIN: {ENGINE.vin}. Built by Boost Barn Motorsports (WO #{ENGINE.work_order}).

Bottom end: {ENGINE.config}, {ENGINE.head_studs} head studs, {ENGINE.oil_pickup}.
Valvetrain: {ENGINE.intake_valves} intake, {ENGINE.exhaust_valves} exhaust, {ENGINE.valve_guides} guides, {ENGINE.springs}, {ENGINE.valve_seals} seals.
Fuel: {ENGINE.injectors} injectors, {ENGINE.fuel_pump} pump, {ENGINE.fuel_rails} rails, {ENGINE.fuel_regulator}. Flex fuel sensor installed.
Turbo: {ENGINE.turbo}. Induction: {ENGINE.intercooler} FMIC, {ENGINE.tgv_housings} TGV housings, {ENGINE.turbo_inlet}.
Cooling: {ENGINE.radiator} radiator, Cylinder 4 cooling mod, {ENGINE.oil_separator}. Full timing service + gasket refresh.
Sensors: {ENGINE.oil_pressure_sensor} oil, {ENGINE.fuel_pressure_sensor} fuel, {ENGINE.map_sensor} MAP, {ENGINE.iat_sensor}.
Electronics: {ENGINE.ecu}, {ENGINE.pdm}, {ENGINE.keypad}, {ENGINE.dash}.

Baselines: Oil {BASELINES.oil_idle_warm_low}-{BASELINES.oil_idle_warm_high} PSI idle, ~10 PSI/1000 RPM. \
Coolant {BASELINES.coolant_normal_low}-{BASELINES.coolant_normal_high}C normal, alert >{BASELINES.coolant_alert}C. \
Fuel base {BASELINES.fuel_base_psi} PSI, rises 1:1 with boost. AFR cruise {BASELINES.afr_cruise}, boost {BASELINES.afr_boost_gas_low}-{BASELINES.afr_boost_gas_high}.

Casting: {ENGINE.casting}, batch {ENGINE.batch_code}, stamps {', '.join(ENGINE.machined_stamps)}.
Installed {INSTALL_DATE}. Body: {BODY_KM_AT_INSTALL:,} km. Engine: 0 km — fresh build, pre-first start."""
