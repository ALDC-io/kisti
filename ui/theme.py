"""KiSTI - Tritium-Heritage Instrument Theme

Aesthetic ref: Sinn 856 UTC / Porsche 917 dash / radium-dial instruments.
Green-tinted white (photoluminescent) — NOT a green colour scheme.
Dark cockpit philosophy: normal = invisible, deviations illuminate.

Palette roles:
  WHITE   → instrument primary  (tick marks, numerals, needle)
  SILVER  → instrument secondary (minor ticks, sub-labels)
  GRAY    → dimmed / dark-cockpit text (normal-state vitals)
  DIM     → subtle lines, grid, ring edges, separators
  RED     → critical warnings only — unchanged
  YELLOW  → caution / warning — unchanged
  HIGHLIGHT → alert-ack / redline amber — unchanged
"""

# === Tritium-Heritage Gauge Palette ===

# Backgrounds
BG_DARK = "#0A0A0A"       # Near-black gauge face
BG_PANEL = "#121212"       # Recessed panel
BG_ACCENT = "#1A1A1A"      # Carbon dark

# STI / Alert Accents — DO NOT CHANGE (safety-critical)
HIGHLIGHT = "#FFB000"      # Amber — redline + alert-ack
RED = "#FF1A1A"            # Critical warnings only
CHERRY = "#CC0000"         # Redline zone (gauge arc)

# Severity / Status — DO NOT CHANGE (safety-critical)
GREEN = "#00CC66"          # OK / optimal (tire, ECU state)
YELLOW = "#FFAA00"         # Caution amber
CYAN = "#00CCFF"           # Digital display cyan

# GT7 Tire Temperature Palette
TIRE_BLUE = "#0077DD"      # Cold tires
TIRE_BLUE_DARK = "#003366" # Cold tires (dim)
TIRE_GREEN = "#00CC66"     # Optimal grip
TIRE_YELLOW = "#FFAA00"    # Getting hot
TIRE_RED = "#FF2222"       # Overheating

# Radar Band Colors (Valentine One)
RADAR_KA = "#FF3333"       # Ka band — highest threat
RADAR_K = "#FFAA00"        # K band — common (door openers)
RADAR_X = "#00AAFF"        # X band — rare / legacy
RADAR_LASER = "#FF00FF"    # Laser — instant threat
RADAR_CLEAR = "#2A3A2A"    # No alerts (tritium dim)

# Text — tritium-heritage substitutions
WHITE = "#D4E8D0"          # Instrument primary: luminescent green-white
SILVER = "#B8D0B8"         # Instrument secondary: minor ticks, sub-labels
GRAY = "#6A8A6A"           # Dimmed / dark-cockpit: normal-state vitals
DIM = "#2A3A2A"            # Subtle lines, grid, ring edges, separators

# Chrome ring — neutral metallic, unaffected by tritium tint
CHROME_LIGHT = "#C0C0C0"   # Chrome ring highlight
CHROME_MID = "#909090"     # Chrome ring mid
CHROME_DARK = "#606060"    # Chrome ring shadow

# Font sizes
FONT_BASE = 14
FONT_HEADER = 18
FONT_BIG = 26

STYLESHEET = f"""
QWidget {{
    background-color: {BG_DARK};
    color: {WHITE};
    font-size: {FONT_BASE}px;
    font-family: "Helvetica", "Arial", "DejaVu Sans", sans-serif;
}}

QMainWindow {{
    background-color: {BG_DARK};
}}

QLabel {{
    background: transparent;
    padding: 0px;
}}

QPushButton {{
    background-color: {BG_PANEL};
    color: {SILVER};
    border: 1px solid {CHROME_DARK};
    border-radius: 4px;
    padding: 8px 12px;
    font-size: {FONT_BASE}px;
    font-weight: bold;
    min-height: 48px;
}}

QPushButton:hover {{
    background-color: {BG_ACCENT};
    border: 1px solid {HIGHLIGHT};
    color: {WHITE};
}}

QPushButton:pressed {{
    background-color: {HIGHLIGHT};
    color: {WHITE};
}}

QPushButton[active="true"] {{
    background-color: {CHERRY};
    border: 2px solid {HIGHLIGHT};
    color: {WHITE};
}}

QDialog {{
    background-color: {BG_DARK};
    border: 2px solid {CHROME_MID};
    border-radius: 8px;
}}

QScrollArea {{
    border: none;
    background: transparent;
}}

QScrollBar:vertical {{
    background: {BG_PANEL};
    width: 6px;
    border-radius: 3px;
}}

QScrollBar::handle:vertical {{
    background: {CHROME_DARK};
    border-radius: 3px;
    min-height: 20px;
}}
"""
