"""KiSTI - Configuration"""

WINDOW_WIDTH = 800
WINDOW_HEIGHT = 480
FULLSCREEN = False
TARGET_DISPLAY = None  # e.g. ":0" -- set via CLI or env

# Update rates (milliseconds)
FAST_TICK_MS = 100   # 10 Hz - temps, position
SLOW_TICK_MS = 1000  # 1 Hz  - GPS, session, findings

# Temperature thresholds (Celsius)
TIRE_TEMP_GREEN_MAX = 90
TIRE_TEMP_YELLOW_MAX = 105
BRAKE_TEMP_GREEN_MAX = 300
BRAKE_TEMP_YELLOW_MAX = 400

# Oil pressure thresholds (PSI)
OIL_PSI_LOW_WARN = 25
OIL_PSI_LOW_CRIT = 15
OIL_PSI_HIGH_WARN = 80
OIL_TEMP_WARN = 130  # Celsius

# Mock data ranges
TIRE_TEMP_BASELINE = (80, 110)
BRAKE_TEMP_BASELINE = (200, 450)
OIL_PSI_BASELINE = (35, 65)
OIL_TEMP_BASELINE = (85, 120)
LAP_DURATION_S = 90

# Valentine One Gen2 Radar
RADAR_TICK_MS = 500       # 2 Hz update rate
RADAR_MOCK_ENABLED = True # Use mock generator (True) or BLE driver (False)
RADAR_SIGNAL_WARN = 3     # Signal strength warning threshold (out of 8)
RADAR_SIGNAL_CRIT = 6     # Signal strength critical threshold (out of 8)

# V1 Gen2 BLE UUIDs (for future real hardware driver)
V1_BLE_SERVICE_UUID = "92A0AFF4-9E05-11E2-AA59-F23C91AEC05E"
V1_BLE_SHORT_UUID = "92A0AFF5-9E05-11E2-AA59-F23C91AEC05E"
V1_BLE_LONG_UUID = "92A0AFF6-9E05-11E2-AA59-F23C91AEC05E"

# Band frequency ranges (MHz)
RADAR_BAND_X = (10500, 10550)
RADAR_BAND_K = (24050, 24250)
RADAR_BAND_Ka = (33400, 36000)   # Wide Ka covers 33.4-36.0 GHz
