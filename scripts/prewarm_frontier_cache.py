#!/usr/bin/env python3
"""KiSTI - Frontier Cache Pre-Warm Script

Queries Claude Haiku API for common automotive and general knowledge
questions, caching responses in DuckDB so they're available offline
at ~2ms latency instead of ~500ms over WiFi.

Requires ANTHROPIC_API_KEY in environment.

Usage:
    python3 -m scripts.prewarm_frontier_cache
    python3 -m scripts.prewarm_frontier_cache --db /data/duckdb/kisti.duckdb
    python3 -m scripts.prewarm_frontier_cache --dry-run
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# Add repo root to path so imports work when run as script
_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from voice.frontier_engine import FrontierLLMEngine

# Common questions organized by category. These are queries that
# would miss persona matching and go to the frontier engine.
PREWARM_QUERIES: list[tuple[str, str]] = [
    # Automotive fundamentals
    ("auto", "Why do Subaru EJ engines have unequal length headers while Porsche boxers use equal length?"),
    ("auto", "What is the difference between open deck and closed deck engine blocks?"),
    ("auto", "How does a turbocharger wastegate work?"),
    ("auto", "What causes turbo lag and how do you reduce it?"),
    ("auto", "What is the purpose of an intercooler?"),
    ("auto", "How does a limited slip differential work?"),
    ("auto", "What is the difference between sequential and parallel twin turbo setups?"),
    ("auto", "Why do performance engines use forged pistons instead of cast?"),
    ("auto", "How does variable valve timing improve engine performance?"),
    ("auto", "What is engine knock and why is it dangerous?"),
    # Subaru / EJ specific
    ("subaru", "What are the common failure points of the EJ257 engine?"),
    ("subaru", "Why does the Subaru EJ engine use an external oil cooler?"),
    ("subaru", "What is the difference between a 5 speed and 6 speed STI transmission?"),
    ("subaru", "How does Subaru DCCD all wheel drive system work?"),
    ("subaru", "What is the ring land failure problem on EJ engines?"),
    # Tuning and modifications
    ("tuning", "What does an electronic boost controller do?"),
    ("tuning", "How do wideband oxygen sensors differ from narrowband?"),
    ("tuning", "What is the purpose of a standalone engine management system?"),
    ("tuning", "How does water methanol injection improve performance?"),
    ("tuning", "What is the difference between MAF and MAP based tuning?"),
    # Suspension and handling
    ("handling", "How do coilovers differ from struts with lowering springs?"),
    ("handling", "What is roll center and why does it matter for handling?"),
    ("handling", "How does camber affect tire wear and cornering grip?"),
    ("handling", "What is the purpose of sway bars and how do adjustable ones work?"),
    # Track and racing
    ("racing", "What is trail braking and when should you use it?"),
    ("racing", "How do you calculate optimal tire pressures for track driving?"),
    ("racing", "What is the racing line and how does it minimize lap time?"),
    ("racing", "What is the difference between understeer and oversteer?"),
    ("racing", "How does brake fade happen and how do you prevent it?"),
    # General STEM
    ("stem", "How does GPS trilateration calculate position?"),
    ("stem", "What is the Bernoulli principle and how does it create downforce?"),
    ("stem", "How do accelerometers measure g-forces?"),
    ("stem", "What is the coefficient of friction and how does temperature affect it?"),
    ("stem", "How does an inertial measurement unit work?"),
]


def collect_queries() -> list[tuple[str, str]]:
    """Return the list of (category, query) tuples for prewarming."""
    return list(PREWARM_QUERIES)


def prewarm(db_path: Path, dry_run: bool = False) -> None:
    """Pre-warm the frontier cache by querying Claude Haiku for each entry.

    Args:
        db_path: Path to DuckDB database file.
        dry_run: If True, list queries without calling the API.
    """
    queries = collect_queries()
    total = len(queries)

    if dry_run:
        print(f"Dry run: {total} queries to cache (no API calls)")
        for i, (cat, query) in enumerate(queries, 1):
            print(f"  [{cat}] {i}. {query}")
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    import duckdb

    conn = duckdb.connect(str(db_path))
    engine = FrontierLLMEngine(api_key=api_key, db_conn=conn)
    engine.start()

    # Wait for initial WiFi check
    time.sleep(2)
    if not engine.wifi_available:
        print("WARNING: WiFi not available — cannot query API")
        engine.stop()
        conn.close()
        sys.exit(1)

    cached = 0
    skipped = 0
    errors = 0
    t0 = time.monotonic()

    for i, (cat, query) in enumerate(queries, 1):
        truncated = query[:60] + ("..." if len(query) > 60 else "")
        resp = engine.query(query)

        if resp is None:
            print(f"  ERROR {i}/{total}: [{cat}] {truncated}")
            errors += 1
        elif resp.tier == "frontier_cache":
            print(f"  SKIP  {i}/{total}: [{cat}] {truncated} (already cached)")
            skipped += 1
        else:
            tokens = resp.tokens if hasattr(resp, "tokens") else 0
            print(f"  CACHE {i}/{total}: [{cat}] {truncated} ({resp.latency_s:.1f}s, {tokens} tokens)")
            cached += 1

        # Small delay between API calls to avoid rate limiting
        if resp and resp.tier == "frontier_live":
            time.sleep(0.5)

    elapsed = time.monotonic() - t0
    stats = engine.cache_stats()
    engine.stop()
    conn.close()

    print(f"\nDone: {cached} cached, {skipped} already cached, {errors} errors")
    print(f"Total cache: {stats['total']} entries, {stats['total_hits']} hits")
    print(f"Elapsed: {elapsed:.1f}s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Pre-warm frontier response cache for KiSTI")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("/data/duckdb/kisti.duckdb"),
        help="DuckDB database path (default: /data/duckdb/kisti.duckdb)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List queries without calling the API",
    )
    args = parser.parse_args()
    prewarm(db_path=args.db, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
