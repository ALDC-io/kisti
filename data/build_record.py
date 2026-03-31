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

from dataclasses import dataclass, field
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

    # Bottom end — pistons & short block
    pistons: str = "Manley H-Tuff Plus Forged"
    bore_mm: float = 99.75   # overbored from factory 99.5 mm
    stroke_mm: float = 79.0
    head_studs: str = "ARP Custom Age DOHC"
    oil_pickup: str = "IAG Upper Windage Tray & Oil Pickup"
    rear_main_seal: str = "OEM"
    oil_pan_gasket: str = "O-Ring Single"
    engine_mounts: str = "STI Group N (left + right)"

    # Valvetrain
    intake_valves: str = "GSC P-D 36mm Chrome Polished (Std)"
    exhaust_valves: str = "GSC P-D 32mm Chrome Polished Super Alloy (Std)"
    valve_guides: str = "GSC Manganese Bronze Intake + Exhaust Stopper Style"
    springs: str = "GSC P-D EJ257 Beehive + Titanium Retainer Kit (factory spring seats)"
    valve_seals: str = "GSC Viton 6mm Stem Seal Set"
    rockers: str = "GSKT-Rocker x4"

    # Induction
    intercooler: str = "COBB Front Mount Intercooler"
    tgv_housings: str = "PrecisionWorks Billet TGV Housing"
    turbo_inlet: str = "Perrin Turbo Inlet Hose Black"
    map_sensor: str = "Cobb 4 Bar Map Sensor Upgrade Kit"
    iat_sensor: str = "GM IAT (relocated to FMIC)"
    air_pump_delete: str = "BB Air Pump Delete Plates"
    ebcs: str = "3 Port EBCS (swapped WRX to STI)"

    # Fuel
    injectors: str = "ID1300"
    injector_pigtails: str = "Injector Pigtails x4"
    fuel_pump: str = "Deatschwerks DW300C Series (under rear passenger seat)"
    fuel_rails: str = "IAG PTFE"
    fuel_regulator: str = "Aeromotive FPR"
    flex_fuel_sensor: bool = True
    flex_fuel_tune: str = "Standalone Flex Fuel Protune (10.72 hrs, E100)"

    # Turbo
    turbo: str = "BCP X400 Turbocharger 400WHP"

    # Exhaust gaskets (Grimmspeed)
    uppipe_gasket: str = "Grimmspeed Uppipe To Turbo"
    lower_uppipe_gasket: str = "Grimmspeed Lower Uppipe"
    exhaust_manifold_gasket: str = "Grimmspeed Head To Exhaust Manifold Dual Port"
    downpipe_gasket: str = "Grimmspeed Downpipe To Catback 2 Bolt 3 Inch"
    turbo_oil_line_gaskets: str = "Turbocharger Oil Line Gasket x2"

    # Cooling / reliability
    cyl4_cooling_mod: bool = True
    radiator: str = "CSF Race Spec 2 Row Aluminum Black"
    oil_separator: str = "IAG Air/Oil Separator (AOS) Black"
    timing_service: str = "Belt, water pump, thermostat RE/RE"
    gasket_refresh: bool = True
    coolant: str = "Super Blue Coolant (12L)"
    engine_oil: str = "Motul X-Clean 5W40 (5L)"

    # Drivetrain
    clutch: str = "Competition Clutch Stage 2 Steelback Brass Plus"
    flywheel: str = "ACT Lightweight Flywheel"
    clutch_line: str = "Clutch Masters Steel Clutch Line"
    trans_fluid: str = "Motul 75W90 Gear Oil (5L)"
    diff_fluid: str = "Motul 75W90 LS (Limited Slip) (1L)"
    brake_fluid: str = "Pentosin Super DOT 4"

    # Suspension / chassis
    front_swaybar: str = "GR Front Swaybar (swapped)"
    rear_swaybar: str = "GR/VA Rear Swaybar (swapped)"
    front_struts: str = "KYB Suspension Front L+R"
    lower_mounts: str = "Fortune Auto Lower Mounts"
    spark_plugs: str = "New (brand TBD on work order)"

    # Sensors (KiSTI critical)
    oil_pressure_sensor: str = "Prosport 0-150 PSI + Galley Plug 1/8 NPT"
    fuel_pressure_sensor: str = "0-100 PSI (wired to passenger side TGV plug)"

    # Electronics
    ecu: str = "Link G5 Neo 4"
    pdm: str = "Link Razor PDM"
    keypad: str = "Link CAN Keypad (8 button)"
    dash: str = "AiM Strada 7\" Street Edition"

    # Build cost
    total_cost: float = 29_607.44
    labour_rate: float = 140.00
    machine_shop_fees: float = 950.00


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
VIN: {ENGINE.vin}. Built by Boost Barn Motorsports (WO #{ENGINE.work_order}). Total build cost: ${ENGINE.total_cost:,.2f}.

Bottom end: {ENGINE.config}, {ENGINE.head_studs} head studs, {ENGINE.oil_pickup}. {ENGINE.engine_mounts} engine mounts.
Valvetrain: {ENGINE.intake_valves} intake, {ENGINE.exhaust_valves} exhaust, {ENGINE.valve_guides} guides, {ENGINE.springs}, {ENGINE.valve_seals} seals.
Fuel: {ENGINE.injectors} injectors, {ENGINE.fuel_pump} pump, {ENGINE.fuel_rails} rails, {ENGINE.fuel_regulator}. {ENGINE.flex_fuel_tune}.
Turbo: {ENGINE.turbo}. Induction: {ENGINE.intercooler}, {ENGINE.tgv_housings}, {ENGINE.turbo_inlet}. {ENGINE.ebcs}.
Drivetrain: {ENGINE.clutch}, {ENGINE.flywheel}, {ENGINE.clutch_line}.
Exhaust: Grimmspeed gasket set (uppipe, exhaust manifold, downpipe to catback).
Cooling: {ENGINE.radiator}, Cylinder 4 cooling mod, {ENGINE.oil_separator}. Full timing service + gasket refresh.
Suspension: {ENGINE.front_swaybar}, {ENGINE.rear_swaybar}, {ENGINE.front_struts}, {ENGINE.lower_mounts}.
Fluids: {ENGINE.engine_oil}, {ENGINE.trans_fluid}, {ENGINE.diff_fluid}, {ENGINE.brake_fluid}, {ENGINE.coolant}.
Sensors: {ENGINE.oil_pressure_sensor} oil, {ENGINE.fuel_pressure_sensor} fuel, {ENGINE.map_sensor} MAP, {ENGINE.iat_sensor}.
Electronics: {ENGINE.ecu}, {ENGINE.pdm}, {ENGINE.keypad}, {ENGINE.dash}.

Baselines: Oil {BASELINES.oil_idle_warm_low}-{BASELINES.oil_idle_warm_high} PSI idle, ~10 PSI/1000 RPM. \
Coolant {BASELINES.coolant_normal_low}-{BASELINES.coolant_normal_high}C normal, alert >{BASELINES.coolant_alert}C. \
Fuel base {BASELINES.fuel_base_psi} PSI, rises 1:1 with boost. AFR cruise {BASELINES.afr_cruise}, boost {BASELINES.afr_boost_gas_low}-{BASELINES.afr_boost_gas_high}.

Casting: {ENGINE.casting}, batch {ENGINE.batch_code}, stamps {', '.join(ENGINE.machined_stamps)}.
Installed {INSTALL_DATE}. Body: {BODY_KM_AT_INSTALL:,} km. Engine: 0 km — fresh build, pre-first start."""


# ========================================================================
# Factory specifications — 2014 Subaru WRX STI (GR chassis) as delivered.
# Used for before/after comparisons in persona responses.
# ========================================================================

@dataclass(frozen=True)
class FactorySpec:
    """Factory specs for the 2014 Subaru WRX STI (GR chassis, USDM)."""

    # Engine
    engine_code: str = "EJ257"
    config: str = "Flat-4 DOHC 16-valve AVCS, open-deck aluminum"
    displacement_cc: int = 2457
    bore_mm: float = 99.5
    stroke_mm: float = 79.0
    compression_ratio: str = "8.2:1"
    hp: int = 305
    hp_rpm: int = 6000
    torque_lb_ft: int = 290
    torque_rpm: int = 4000
    redline_rpm: int = 6700
    rev_limiter_rpm: int = 7200
    fuel_octane_min: int = 91

    # Turbo
    turbo: str = "IHI VF48 (twin-scroll, journal bearing)"
    factory_boost_psi: float = 14.7
    wastegate: str = "Internal swing-valve, ECU-controlled 3-port solenoid"

    # Transmission
    trans: str = "6-speed manual (TY856WB9AA)"
    gear_1: float = 3.636
    gear_2: float = 2.235
    gear_3: float = 1.521
    gear_4: float = 1.137
    gear_5: float = 0.971
    gear_6: float = 0.756
    gear_reverse: float = 3.545
    final_drive: float = 3.900

    # Drivetrain
    dccd: str = "Planetary gear center diff, electromagnetic + mechanical LSD"
    default_split: str = "41% front / 59% rear"
    front_diff: str = "Helical limited-slip"
    rear_diff: str = "Torsen Type-1 limited-slip"

    # Brakes
    front_brake: str = "Brembo 4-piston monoblock, 326 mm x 30 mm ventilated cross-drilled"
    rear_brake: str = "Brembo 2-piston monoblock, 316 mm x 20 mm ventilated cross-drilled"
    brake_fluid: str = "DOT 4"

    # Suspension
    front_suspension: str = "MacPherson strut, inverted"
    front_spring_rate: str = "4.0 kg/mm (224 lb/in)"
    front_sway_bar_mm: int = 24
    rear_suspension: str = "Double wishbone (multi-link) with pillow ball mounts"
    rear_spring_rate: str = "3.5 kg/mm (196 lb/in)"
    rear_sway_bar_mm: int = 19

    # Wheels & tires
    wheels: str = "18 x 8.5J ET55, 5x114.3"
    tires: str = "245/40R18 Dunlop SP Sport Maxx RT"

    # Weight & dimensions
    curb_weight_kg: int = 1536
    curb_weight_lbs: int = 3386
    weight_distribution: str = "60% front / 40% rear"
    wheelbase_mm: int = 2625
    track_front_mm: int = 1530
    track_rear_mm: int = 1530
    length_mm: int = 4580
    width_mm: int = 1795
    height_mm: int = 1470
    ground_clearance_mm: int = 155

    # Fuel system
    injectors: str = "Denso 565 cc top-feed"
    fuel_pump: str = "In-tank electric, ~255 LPH (Denso)"
    fuel_rail_psi: float = 43.5
    fuel_tank_liters: int = 60

    # Cooling
    radiator: str = "Aluminum core, plastic end tanks, 2-row"
    intercooler: str = "Top-mount air-to-air (TMIC)"
    oil_cooler: str = "Air-to-oil, front-mounted"
    coolant_capacity_liters: float = 6.2
    thermostat_open_c: float = 76.5

    # Electrical
    alternator_amps: int = 110
    spark_plugs: str = "NGK ILFR6B iridium (gap 0.7-0.8 mm)"
    ecu: str = "Denso"

    # Oil
    oil_spec: str = "5W-30"
    oil_capacity_liters: float = 4.7

    # Performance
    zero_to_sixty_s: str = "4.7-5.0"
    quarter_mile_s: str = "13.2-13.5 @ 102-104 mph"
    top_speed_mph: int = 155
    lateral_g: str = "0.90-0.95"

    # Known weaknesses
    known_weaknesses: tuple = (
        "Ringland failure under detonation (open-deck block)",
        "Rod bearing spin without oil pressure monitoring",
        "Head gasket weep (less common on turbo EJ)",
        "5th gear synchro weak under hard shifting",
    )


FACTORY = FactorySpec()


def factory_vs_build() -> str:
    """Generate a factory vs current build comparison."""
    return f"""Factory 2014 STI vs current build:
Engine: {FACTORY.engine_code} open-deck {FACTORY.hp} hp → IAG 750 closed-deck {ENGINE.current_tune_whp} WHP ({ENGINE.power_capability_bhp} bhp capable).
Block: Factory open-deck aluminum → IAG 750 closed-deck forged. {ENGINE.pistons}, overbored {ENGINE.bore_mm} mm (factory {FACTORY.bore_mm} mm).
Turbo: {FACTORY.turbo} @ {FACTORY.factory_boost_psi} PSI → {ENGINE.turbo}.
Fuel: {FACTORY.injectors} → {ENGINE.injectors}, {ENGINE.fuel_pump}, {ENGINE.fuel_regulator}. Flex fuel ready.
Cooling: Factory 2-row plastic/aluminum → {ENGINE.radiator}, Cyl 4 cooling mod, {ENGINE.oil_separator}.
Intercooler: Factory TMIC → {ENGINE.intercooler} (front mount).
Clutch: Factory → {ENGINE.clutch}, {ENGINE.flywheel}.
ECU: {FACTORY.ecu} → {ENGINE.ecu} standalone.
Brakes: Factory {FACTORY.front_brake} retained. Fluid upgraded to {ENGINE.brake_fluid}.
Suspension: Factory inverted struts retained. Swaybars swapped to GR spec. {ENGINE.lower_mounts}.
Known factory weaknesses addressed: closed-deck block (ringlands), ARP studs (head gaskets), aftermarket oil pickup (bearing protection)."""
