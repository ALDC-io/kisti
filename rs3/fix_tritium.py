#!/usr/bin/env python3
"""
fix_tritium.py — AiM Race Studio 3 tritium-heritage theme patcher
Target: C:\\AIM_SPORT\\RaceStudio3

Handles .aimdev2 (ZIP+XML), .rs3db (SQLite), and loose .xml project files.

Fixes applied in a single pass:
  1. Tritium colour substitutions (white/near-white → green-white palette)
  2. Ring gap closure (bezel rings forced to 360° sweep — no more holes)
  3. Needle colour persistence (orange amber written into XML AND .aimdev2
     sidecar so RS3 transmit cache cannot revert it)

Usage (run on Windows with RS3 fully closed):
    python fix_tritium.py
    python fix_tritium.py --path "C:\\AIM_SPORT\\RaceStudio3"
    python fix_tritium.py --dry-run   # preview changes, write nothing

Workflow:
  1. Close Race Studio 3 completely
  2. Run this script
  3. Reopen Race Studio 3
  4. Transmit to device immediately (do not save first — saving re-caches)
"""

import argparse
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Callable

# ---------------------------------------------------------------------------
# Tritium palette (hex, no '#')
# ---------------------------------------------------------------------------
TRITIUM = {
    "PRIMARY":    "D4E8D0",  # Instrument primary: tick marks, numerals, needle
    "SECONDARY":  "B8D0B8",  # Instrument secondary: minor ticks, sub-labels
    "DIMMED":     "6A8A6A",  # Dark-cockpit text: normal-state vitals
    "LINES":      "2A3A2A",  # Subtle lines, grid, ring separators
    "FACE":       "0A0A0A",  # Near-black gauge face background
    # Safety-critical — DO NOT substitute
    "AMBER_ALERT": "FFB000", # Redline + alert-ack amber
    "CAUTION":    "FFAA00",  # Standard caution amber
    "CRITICAL":   "FF1A1A",  # Warning red (unchanged)
}

# Old → new colour mapping (lowercase hex, no '#')
# Keys are the colours to REPLACE; values are what to replace with.
# Safety-critical reds/ambers are NOT in this table — they are never touched.
COLOUR_MAP = {
    # Pure white
    "ffffff": TRITIUM["PRIMARY"],
    # Near-whites (common RS3 defaults)
    "f0f0f0": TRITIUM["PRIMARY"],
    "e8e8e8": TRITIUM["PRIMARY"],
    "e0e0e0": TRITIUM["PRIMARY"],
    "d8d8d8": TRITIUM["PRIMARY"],
    "d0d0d0": TRITIUM["SECONDARY"],
    "c8c8c8": TRITIUM["SECONDARY"],
    "c0c0c0": TRITIUM["SECONDARY"],
    "b8b8b8": TRITIUM["SECONDARY"],
    "b0b0b0": TRITIUM["SECONDARY"],
    "a8a8a8": TRITIUM["SECONDARY"],
    "a0a0a0": TRITIUM["SECONDARY"],
    # Mid-greys → dimmed
    "989898": TRITIUM["DIMMED"],
    "909090": TRITIUM["DIMMED"],
    "888888": TRITIUM["DIMMED"],
    "808080": TRITIUM["DIMMED"],
    # Dark greys → lines
    "505050": TRITIUM["LINES"],
    "484848": TRITIUM["LINES"],
    "404040": TRITIUM["LINES"],
    "383838": TRITIUM["LINES"],
    "333333": TRITIUM["LINES"],
    "303030": TRITIUM["LINES"],
    "282828": TRITIUM["LINES"],
    "202020": TRITIUM["LINES"],
    # Pure black face (leave as-is — already correct)
    # "000000": TRITIUM["FACE"],  # Don't replace — transparency is black too
}

# ARGB integer variants (AiM stores colours as 0xAARRGGBB signed/unsigned int)
# Built dynamically in _build_argb_map()

# Needle colour: amber — must survive RS3 cache rewrite
NEEDLE_HEX = "FFB000"                         # Amber needle
NEEDLE_ARGB_INT = int("FF" + NEEDLE_HEX, 16)  # 0xFFFFB000 = 4294946816

# Elements that are safety-critical — never recolour (substring match on type attr)
SAFETY_TYPES = {"redzone", "warningzone", "alertzone", "alarm", "limit"}

# XML attributes that carry colour values
COLOUR_ATTRS = {
    "color", "colour", "forecolor", "backcolor", "fillcolor", "bordercolor",
    "needlecolor", "labelcolor", "textcolor", "tickcolor", "arccolor",
    "Color", "ForeColor", "BackColor", "FillColor", "BorderColor",
    "NeedleColor", "LabelColor", "TextColor", "TickColor", "ArcColor",
    "BackgroundColor", "ValueColor", "MinorTickColor", "MajorTickColor",
}

# XML attributes that control arc/sweep geometry
SWEEP_ATTRS = {
    "sweepAngle", "SweepAngle", "sweep_angle", "arcSweep", "ArcSweep",
    "spanAngle", "SpanAngle", "backgroundSweep", "BackgroundSweep",
}
START_ATTRS = {
    "startAngle", "StartAngle", "start_angle", "arcStart", "ArcStart",
    "backgroundStart", "BackgroundStart",
}

# Element types that are decorative rings/bezels (should be 360°)
# Deliberately excludes "frame" — too greedy (matches keyframe, TimeFrame, etc.)
RING_TYPES = {
    "ring", "bezel", "circlebackground", "outerring", "chromering",
    "bezeldecor", "gaugeframe", "gaugering",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hex_to_argb_int(hex6: str, alpha: int = 0xFF) -> int:
    """Convert 6-char hex string to ARGB integer (AiM format)."""
    r = int(hex6[0:2], 16)
    g = int(hex6[2:4], 16)
    b = int(hex6[4:6], 16)
    return (alpha << 24) | (r << 16) | (g << 8) | b


def _argb_int_to_hex6(value: int) -> str:
    """Convert ARGB integer to 6-char lowercase hex (drops alpha)."""
    r = (value >> 16) & 0xFF
    g = (value >> 8) & 0xFF
    b = value & 0xFF
    return f"{r:02x}{g:02x}{b:02x}"


def _build_argb_map() -> dict[int, int]:
    """Build ARGB integer → ARGB integer substitution map."""
    result = {}
    for old_hex, new_hex in COLOUR_MAP.items():
        old_int = _hex_to_argb_int(old_hex)
        new_int = _hex_to_argb_int(new_hex)
        result[old_int] = new_int
        # Also handle semi-transparent variants (e.g. alpha=0xCC)
        for alpha in (0xCC, 0xAA, 0x88, 0x66):
            result[_hex_to_argb_int(old_hex, alpha)] = _hex_to_argb_int(new_hex, alpha)
    return result

ARGB_MAP = _build_argb_map()


def _is_safety_element(element_type: str) -> bool:
    """Return True if this element type is safety-critical (never recolour)."""
    t = element_type.lower().replace(" ", "").replace("-", "").replace("_", "")
    return any(s in t for s in SAFETY_TYPES)


def _sub_colour_hex(match: re.Match) -> str:
    """Regex substitution callback for hex colour strings."""
    prefix = match.group(1)   # '#' or '0x' or ''
    colour = match.group(2).lower()
    replacement = COLOUR_MAP.get(colour)
    if replacement:
        return prefix + replacement.upper()
    return match.group(0)


# ---------------------------------------------------------------------------
# XML processing (string-level — avoids lxml dependency)
# ---------------------------------------------------------------------------

def _process_xml(xml: str, dry_run: bool = False) -> tuple[str, int]:
    """
    Apply all fixes to an RS3 XML string.
    Returns (modified_xml, change_count).
    """
    changes = 0

    # --- 1. Colour substitutions ---
    # Hex colours: #RRGGBB or #AARRGGBB  (case-insensitive)
    def _sub_hex(m: re.Match) -> str:
        nonlocal changes
        orig = m.group(0)
        prefix = m.group(1)
        colour = m.group(2).lower()
        # 8-char AARRGGBB: strip alpha prefix then look up
        if len(colour) == 8:
            alpha_str = colour[:2]
            hex6 = colour[2:]
        else:
            alpha_str = ""
            hex6 = colour
        replacement = COLOUR_MAP.get(hex6)
        if replacement:
            changes += 1
            return prefix + alpha_str + replacement.upper()
        return orig

    xml = re.sub(
        r"(#|0x|0X)([0-9A-Fa-f]{6}(?:[0-9A-Fa-f]{2})?)\b",
        _sub_hex,
        xml,
    )

    # Decimal ARGB integers in XML attributes (e.g. color="-16777216")
    def _sub_decimal(m: re.Match) -> str:
        nonlocal changes
        orig = m.group(0)
        attr = m.group(1)
        quote = m.group(2)
        raw = m.group(3)
        try:
            val = int(raw)
            # Normalise to unsigned 32-bit
            if val < 0:
                val = val & 0xFFFFFFFF
            new_val = ARGB_MAP.get(val)
            if new_val is not None:
                # Preserve sign if original was negative
                if int(raw) < 0:
                    new_val = new_val - 0x100000000
                changes += 1
                return f'{attr}={quote}{new_val}{quote}'
        except ValueError:
            pass
        return orig

    colour_attr_re = "|".join(re.escape(a) for a in COLOUR_ATTRS)
    xml = re.sub(
        rf'({colour_attr_re})=(["\'])(-?\d{{4,12}})\2',
        _sub_decimal,
        xml,
    )

    # --- 2. Needle colour fix ---
    # Force needle colour to amber (FFB000). Skip if current value is already a
    # safety-critical red — a red needle means a warning-state gauge, leave it alone.
    _SAFETY_NEEDLE_REDS = {"ff1a1a", "ff0000", "cc0000", "ff3333", "e60000"}

    def _fix_needle(m: re.Match) -> str:
        nonlocal changes
        attr = m.group(1)
        quote = m.group(2)
        old_val = m.group(3)
        # Detect if current value is a safety red — hex or decimal ARGB
        old_lower = old_val.lower().lstrip("#")
        if len(old_lower) == 6 and old_lower in _SAFETY_NEEDLE_REDS:
            return m.group(0)  # leave red warning needles alone
        if len(old_lower) == 8 and old_lower[2:] in _SAFETY_NEEDLE_REDS:
            return m.group(0)
        # Convert amber to ARGB decimal if attribute uses decimal format
        if old_val.lstrip("-").isdigit():
            new_val = str(NEEDLE_ARGB_INT)
        else:
            new_val = "#FF" + NEEDLE_HEX
        if old_val != new_val:
            changes += 1
        return f'{attr}={quote}{new_val}{quote}'

    xml = re.sub(
        r'([Nn]eedle[Cc]olor|NEEDLECOLOR|needle_color)=(["\'])([^"\']+)\2',
        _fix_needle,
        xml,
    )

    # --- 3. Ring gap fix ---
    # Find ring/bezel background elements and force sweepAngle to 360.
    # These are purely decorative chrome rings — a full circle has no gap.
    #
    # Pattern: element has type attr matching RING_TYPES AND a sweep/span
    # attribute with value < 360.  We set it to 360 and startAngle to 0.

    def _fix_ring_sweep(m: re.Match) -> str:
        """Callback for a single XML opening tag that is a ring/bezel element."""
        nonlocal changes
        tag_text = m.group(0)
        tag_lower = tag_text.lower()

        # Check if this is a ring/bezel type
        type_match = re.search(r'type=["\']([^"\']+)["\']', tag_text, re.IGNORECASE)
        elem_type = (type_match.group(1) if type_match else "").lower()
        # Also check element name itself
        tag_name_match = re.match(r'<(\w+)', tag_text)
        tag_name = (tag_name_match.group(1) if tag_name_match else "").lower()

        is_ring = any(rt in elem_type for rt in RING_TYPES) or \
                  any(rt in tag_name for rt in RING_TYPES)
        if not is_ring:
            return tag_text

        modified = tag_text

        # Fix sweepAngle / spanAngle
        for attr in SWEEP_ATTRS:
            pattern = rf'({re.escape(attr)})=["\'](\d+(?:\.\d+)?)["\']'
            def _set_360(ma: re.Match, _attr=attr) -> str:
                nonlocal changes
                old = ma.group(2)
                if float(old) < 359.9:
                    changes += 1
                    return f'{ma.group(1)}="360"'
                return ma.group(0)
            modified = re.sub(pattern, _set_360, modified, flags=re.IGNORECASE)

        # Fix startAngle to 0 so the ring starts at 3-o-clock (standard)
        for attr in START_ATTRS:
            pattern = rf'({re.escape(attr)})=["\']([^"\']+)["\']'
            def _set_start0(ma: re.Match) -> str:
                nonlocal changes
                if ma.group(2).strip() != "0":
                    changes += 1
                    return f'{ma.group(1)}="0"'
                return ma.group(0)
            modified = re.sub(pattern, _set_start0, modified, flags=re.IGNORECASE)

        return modified

    # Match opening XML tags (potentially multi-line)
    xml = re.sub(r'<[A-Za-z][^>]*>', _fix_ring_sweep, xml)

    return xml, changes


# ---------------------------------------------------------------------------
# File format handlers
# ---------------------------------------------------------------------------

def _process_xml_file(path: Path, dry_run: bool) -> int:
    """Process a single .xml file in-place. Returns change count."""
    original = path.read_text(encoding="utf-8", errors="replace")
    modified, changes = _process_xml(original, dry_run)
    if changes and not dry_run:
        backup = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, backup)
        path.write_text(modified, encoding="utf-8")
        print(f"  {path.name}: {changes} changes  (backup → {backup.name})")
    elif changes:
        print(f"  [dry-run] {path.name}: {changes} changes would be made")
    else:
        print(f"  {path.name}: no changes needed")
    return changes


def _process_aimdev2(path: Path, dry_run: bool) -> int:
    """
    Process a .aimdev2 ZIP archive in-place.
    Edits ALL XML files inside — including sidecar dev_* files —
    so RS3's transmit cache cannot revert colour changes.
    Returns total change count.
    """
    total_changes = 0
    print(f"\nProcessing {path.name} (ZIP archive)…")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Extract all
        with zipfile.ZipFile(path, "r") as zf:
            zf.extractall(tmp)

        # Process every XML-like file inside
        for xml_path in tmp.rglob("*"):
            if xml_path.is_dir():
                continue
            suffix = xml_path.suffix.lower()
            if suffix not in {".xml", ".page", ".layout", ".config", ".gauge"}:
                # Also try files with no extension that look like XML
                try:
                    sniff = xml_path.read_bytes()[:5]
                    if not sniff.startswith(b"<?xml") and not sniff.startswith(b"<"):
                        continue
                except OSError:
                    continue

            try:
                original = xml_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            modified, changes = _process_xml(original, dry_run)
            if changes:
                total_changes += changes
                inner = xml_path.relative_to(tmp)
                if not dry_run:
                    xml_path.write_text(modified, encoding="utf-8")
                    print(f"  [{inner}]: {changes} changes")
                else:
                    print(f"  [dry-run] [{inner}]: {changes} changes would be made")

        if not dry_run and total_changes:
            # Back up original
            backup = path.with_suffix(".aimdev2.bak")
            shutil.copy2(path, backup)
            print(f"  Backup saved → {backup.name}")

            # Repack ZIP
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf_out:
                for f in tmp.rglob("*"):
                    if f.is_file():
                        zf_out.write(f, f.relative_to(tmp))
            print(f"  {path.name}: repacked with {total_changes} total changes")

    return total_changes


def _process_sqlite(path: Path, dry_run: bool) -> int:
    """
    Process a .rs3db SQLite database.
    Scans ALL text columns for colour values and substitutes in-place.
    Returns total change count.
    """
    total_changes = 0
    print(f"\nProcessing {path.name} (SQLite database)…")

    if not dry_run:
        backup = path.with_suffix(".rs3db.bak")
        shutil.copy2(path, backup)
        print(f"  Backup saved → {backup.name}")

    conn = sqlite3.connect(str(path) if not dry_run else ":memory:")
    if dry_run:
        # Open real DB read-only by attaching
        conn.close()
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)

    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cur.fetchall()]

        for table in tables:
            cur.execute(f"PRAGMA table_info({table})")
            cols = cur.fetchall()
            text_cols = [c[1] for c in cols if c[2].upper() in ("TEXT", "VARCHAR", "")]

            for col in text_cols:
                cur.execute(f"SELECT rowid, {col} FROM {table} WHERE {col} IS NOT NULL")
                rows = cur.fetchall()
                for rowid, value in rows:
                    if not isinstance(value, str):
                        continue
                    modified, changes = _process_xml(value)
                    if changes:
                        total_changes += changes
                        if not dry_run:
                            conn.execute(
                                f"UPDATE {table} SET {col}=? WHERE rowid=?",
                                (modified, rowid),
                            )
                        else:
                            print(f"  [dry-run] table={table} col={col} rowid={rowid}: "
                                  f"{changes} changes")

            # Also handle integer colour columns by name
            int_cols = [c[1] for c in cols if c[2].upper() in ("INTEGER", "INT", "BIGINT")]
            colour_int_cols = [c for c in int_cols
                               if any(k in c.lower() for k in ("color", "colour"))]
            for col in colour_int_cols:
                cur.execute(f"SELECT rowid, {col} FROM {table} WHERE {col} IS NOT NULL")
                for rowid, value in cur.fetchall():
                    if not isinstance(value, int):
                        continue
                    unsigned = value & 0xFFFFFFFF
                    new_val = ARGB_MAP.get(unsigned)
                    if new_val is not None:
                        total_changes += 1
                        if not dry_run:
                            conn.execute(
                                f"UPDATE {table} SET {col}=? WHERE rowid=?",
                                (new_val, rowid),
                            )
                        else:
                            old_hex = _argb_int_to_hex6(unsigned)
                            new_hex = _argb_int_to_hex6(new_val)
                            print(f"  [dry-run] table={table} col={col} rowid={rowid}: "
                                  f"#{old_hex.upper()} → #{new_hex.upper()}")

        if not dry_run:
            conn.commit()
            print(f"  {path.name}: {total_changes} total changes committed")
    finally:
        conn.close()

    return total_changes


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(root: Path, dry_run: bool) -> None:
    print(f"\nfix_tritium.py — AiM RS3 tritium theme patcher")
    print(f"Target directory: {root}")
    print(f"Mode: {'DRY RUN (no files written)' if dry_run else 'LIVE (files will be modified)'}\n")

    if not root.exists():
        sys.exit(f"ERROR: directory not found: {root}")

    # Collect all patchable files
    aimdev2_files = list(root.rglob("*.aimdev2"))
    rs3db_files = list(root.rglob("*.rs3db"))
    # Include all loose XML files — .aimdev2 contents live in a tempdir during
    # extraction so there is no collision with files already in root.
    xml_files = list(root.rglob("*.xml"))

    if not (aimdev2_files or rs3db_files or xml_files):
        print("No .aimdev2, .rs3db, or .xml files found in that directory.")
        print("Make sure Race Studio 3 is closed and the path is correct.")
        sys.exit(1)

    grand_total = 0

    for f in aimdev2_files:
        grand_total += _process_aimdev2(f, dry_run)

    for f in rs3db_files:
        grand_total += _process_sqlite(f, dry_run)

    for f in xml_files:
        grand_total += _process_xml_file(f, dry_run)

    print(f"\nTotal changes: {grand_total}")
    if not dry_run and grand_total:
        print("\nNext steps:")
        print("  1. Reopen Race Studio 3")
        print("  2. Transmit to device IMMEDIATELY (do not Save first — saving re-caches)")
        print("  3. Verify on device: rings should be complete circles, needle should be amber")
    elif dry_run:
        print("\nRun without --dry-run to apply changes.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply tritium-heritage theme to AiM Race Studio 3 project files."
    )
    parser.add_argument(
        "--path",
        default=r"C:\AIM_SPORT\RaceStudio3",
        help="Path to Race Studio 3 project directory (default: C:\\AIM_SPORT\\RaceStudio3)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing any files",
    )
    args = parser.parse_args()
    run(Path(args.path), args.dry_run)


if __name__ == "__main__":
    main()
