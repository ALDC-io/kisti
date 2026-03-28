#!/usr/bin/env python3
"""KiSTI - Ingest Boost Barn Work Order into Edge Memory

Parses the work order and creates edge memories for each major
build component and service event. These memories are available
to the co-driver for conversational context.

Usage:
    python3 scripts/ingest_build_docs.py [--db-path /data/duckdb/kisti.duckdb]
"""

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("kisti.ingest")

DEFAULT_DB_PATH = Path("/data/duckdb/kisti.duckdb")
DEV_DB_PATH = Path("/tmp/kisti_build_ingest.duckdb")


# Full work order data extracted from Boost Barn WO #15562
WORK_ORDER = {
    "number": 15562,
    "date": "2026-03-27",
    "provider": "Boost Barn Motorsports",
    "address": "3924 256 St, Aldergrove, BC V4W2A4",
    "phone": "(604) 613-4751",
    "model": "2014 Subaru Impreza WRX (STI)",
    "vin": "JF1GR8H62EL215094",
    "odometer_km": 113736,
    "total": 29607.44,
    "labour_rate": 140.00,
}

# Each build memory: (content, tags, visibility)
BUILD_MEMORIES = [
    # Engine core
    (
        "IAG 750 EJ25 Closed Deck Short Block installed. Serial IAG-14894. "
        "$6,899 part + $4,200 labour (30 hrs head gasket replacement turbo). "
        "Includes timing belt, water pump, thermostat RE/RE. Machine shop fees $950.",
        "engine,iag,short-block,bottom-end,install",
        "team",
    ),
    (
        "ARP Custom Age DOHC Head Stud Kit installed. $1,049. "
        "Critical for boost — holds head gasket under high cylinder pressure.",
        "engine,arp,head-studs,bottom-end",
        "team",
    ),
    (
        "IAG Upper Windage Tray & Oil Pickup installed. $315. "
        "Note: 2.0L oil pans require 2.5L oil pan and dipstick with IAG pickup.",
        "engine,iag,oil-pickup,windage-tray",
        "team",
    ),
    # Valvetrain
    (
        "GSC P-D 36mm Chrome Polished Intake Valves (Std) Set of 8 installed. $199.99. "
        "GSC P-D 32mm Chrome Polished Super Alloy Exhaust Valves (Std) Set of 8. $359. "
        "GSC Beehive Springs with Titanium Retainer Kit (factory spring seats). $559.",
        "valvetrain,gsc,valves,springs,titanium",
        "team",
    ),
    (
        "GSC Manganese Bronze Valve Guides installed — intake ($59) and exhaust ($59) stopper style. "
        "GSC Viton 6mm Valve Stem Seal Set. $19.50. GSKT-Rocker x4. $39.",
        "valvetrain,gsc,valve-guides,seals,rockers",
        "team",
    ),
    # Turbo + induction
    (
        "BCP X400 Turbocharger 400WHP installed. $2,399. "
        "Perrin Turbo Inlet Hose Black. $379. "
        "BB Air Pump Delete Plates. $60.",
        "turbo,bcp,x400,induction",
        "team",
    ),
    (
        "COBB Front Mount Intercooler installed. $3,450 + 4.5 hrs labour ($630). "
        "Bumper modification not included in work order.",
        "intercooler,cobb,fmic,induction",
        "team",
    ),
    (
        "PrecisionWorks Billet TGV Housing installed. $469. "
        "3 Port EBCS swapped from WRX to STI (0 hrs — direct swap).",
        "induction,tgv,ebcs,precisionworks",
        "team",
    ),
    # Fuel system
    (
        "ID1300 Injectors installed. $1,312.99 + Injector Pigtails x4 ($89.48). "
        "1.5 hrs labour ($210) as part of motor rebuild.",
        "fuel,injectors,id1300",
        "team",
    ),
    (
        "Deatschwerks DW300C Fuel Pump with Install Kit installed. $259. "
        "Located under rear passenger seat. 2 hrs labour ($280).",
        "fuel,pump,dw300c,deatschwerks",
        "team",
    ),
    (
        "Standalone Flex Fuel Protune completed. 10.72 hrs ($1,715.20). "
        "E100 fuel used for tuning — 40L ($136). "
        "Motorsports features (launch control, flat foot shifting, anti lag) available separately.",
        "tune,flex-fuel,protune,e100",
        "team",
    ),
    # Sensors
    (
        "Oil Pressure Sensor 0-150 PSI installed. $150.99 + Prosport Galley Plug 1/8 NPT ($19). "
        "Wired to Link ECU via factory MAF sensor wiring. 2 hrs labour ($280).",
        "sensor,oil-pressure,150psi,link-ecu",
        "team",
    ),
    (
        "Fuel Pressure Sensor 0-100 PSI installed. $150.99. "
        "Wired to passenger side TGV plug. 1.5 hrs labour ($210). "
        "May require more time if TGV needs deletion/removal.",
        "sensor,fuel-pressure,100psi,link-ecu",
        "team",
    ),
    (
        "Cobb 4 Bar Map Sensor Upgrade Kit installed. $301.30. 0.3 hrs labour ($42).",
        "sensor,map,4-bar,cobb",
        "team",
    ),
    # Cooling
    (
        "CSF Race Spec 2 Row Aluminum Radiator BLACK installed. $635. "
        "Cylinder 4 Cooling Mod. $77. IAG Air/Oil Separator (AOS) Black. $620. "
        "AOS install 2 hrs labour ($280). Colour options: Black, Red, Neon Yellow.",
        "cooling,csf,radiator,cyl4,aos,iag",
        "team",
    ),
    # Drivetrain
    (
        "Competition Clutch Stage 2 Steelback Brass Plus Clutch Kit installed. $790. "
        "ACT Lightweight Flywheel. $659. Clutch Masters Steel Clutch Line. $61.29.",
        "drivetrain,clutch,flywheel,act,competition-clutch",
        "team",
    ),
    (
        "STI Group N Engine Mounts installed — right ($151.81) and left ($151.81). "
        "Direct OEM replacement, improved NVH over worn originals.",
        "drivetrain,engine-mounts,group-n",
        "team",
    ),
    # Suspension
    (
        "GR Front Swaybar swapped between cars. 3 hrs labour ($420). "
        "GR/VA Rear Swaybar swapped. 3 hrs labour ($420). "
        "Fortune Auto Lower Mounts. $278.60. "
        "KYB Suspension Front Struts L+R. $189.60 each.",
        "suspension,swaybar,kyb,fortune-auto,struts",
        "team",
    ),
    # Fluids + service
    (
        "Full fluid service at build: Motul X-Clean 5W40 (5L, $64.97). "
        "Super Blue Coolant (12L). Motul 75W90 Gear Oil (5L, $139.95 trans). "
        "Motul 75W90 LS (1L, $34.97 rear diff). "
        "Pentosin Super DOT 4 Brake Fluid — bled brakes STI + WRX, bled clutch STI + WRX.",
        "fluids,oil,coolant,brake-fluid,motul,pentosin",
        "team",
    ),
    # Gaskets
    (
        "Full Grimmspeed gasket set installed: Uppipe to Turbo ($28.81), "
        "Lower Uppipe ($28), Head to Exhaust Manifold Dual Port ($40.67), "
        "Downpipe to Catback 2 Bolt 3 Inch ($40.67). "
        "Plus OEM turbo head gaskets x2 ($189.98), valve cover gaskets L+R ($54.26), "
        "cam seals x4 ($40.56), AVCS cam seals x4 ($40.56), AVCS banjo bolt crush washers x10 ($15). "
        "Rear main seal, oil pump seal, crankshaft seal, camshaft seal — all OEM.",
        "gaskets,grimmspeed,oem,seals",
        "team",
    ),
    # Alignment + misc
    (
        "Alignment x2 completed. $195 each ($390 total). "
        "Spark plugs replaced ($70). "
        "Labour: inspect cat in downpipe ($140), swap front brake pads WRX↔STI ($140). "
        "Mount & Balance tires on Apex wheels (tires TBD). $140.",
        "alignment,brakes,tires,apex,service",
        "team",
    ),
]


def main():
    parser = argparse.ArgumentParser(description="Ingest Boost Barn build docs into edge memory")
    parser.add_argument("--db-path", type=str, default=None)
    args = parser.parse_args()

    db_path = Path(args.db_path) if args.db_path else DEFAULT_DB_PATH
    if not db_path.exists():
        db_path = DEV_DB_PATH
        log.info("Using dev DB: %s", db_path)

    from data.duckdb_store import DuckDBStore
    from data.edge_memory import EdgeMemory

    store = DuckDBStore(db_path=db_path)
    store.open()
    mem = EdgeMemory(db_store=store, embedder=None)
    mem.initialize()

    # Check if already ingested
    existing = mem.search_by_tags(["boost-barn-wo-15562"], limit=1)
    if existing:
        log.info("Work order already ingested (%d memories with tag). Skipping.", len(existing))
        store.close()
        return

    # Ingest build memories
    count = 0
    for content, tags, visibility in BUILD_MEMORIES:
        full_tags = f"{tags},boost-barn-wo-15562"
        mem.remember(
            content=content,
            memory_type="maintenance",
            source="work_order",
            tags=full_tags,
            importance=0.8,
            visibility=visibility,
        )
        count += 1

    # Record the overall build as a service event
    store.record_service_event(
        event_type="engine_build",
        description="Complete engine build — IAG 750 Closed Deck, BCP X400 turbo, flex fuel protune. Boost Barn WO #15562.",
        odometer_km=113736,
        engine_km=0,
        parts="IAG-14894 short block, BCP X400, ID1300, DW300C, COBB FMIC, Competition Clutch Stage 2, ACT flywheel, CSF radiator, GSC valvetrain",
        cost=29607.44,
        provider="Boost Barn Motorsports",
        notes="30 hrs head gasket labour + 10.72 hrs flex fuel protune. E100 tuning fuel. Machine shop $950.",
    )

    log.info("Ingested %d build memories + 1 service event", count)
    log.info("Memory stats: %s", mem.stats())
    store.close()


if __name__ == "__main__":
    main()
