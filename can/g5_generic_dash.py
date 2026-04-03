"""KiSTI — Link G5 Generic Dash CAN parser

Decodes the Link G5 Neo 4 Generic Dash multiplexed CAN stream.

Protocol (PCLink defaults — VERIFY against raw CAN sniff before trusting):
  - Single CAN ID (default 0x3E8 = 1000 decimal, configurable in PCLink CAN Setup)
  - Byte[0]: frame index (0–13)
  - Byte[1]: always 0x00 (reserved/padding)
  - Bytes [2:8]: three little-endian signed int16 signal values

Frame layout (byte[0] = frame index):
  Frame 0: RPM (raw ×1), MAP (kPa×10), TPS (%×10)
  Frame 1: CLT (°C×10), IAT (°C×10), Lambda1 (λ×1000)
  Frame 2: OilPress (kPa×10), OilTemp (°C×10), FuelPress (kPa×10)
  Frame 3: Battery (V×100), InjDuty (%×10), Ethanol (%×10)
  Frame 4: Gear (raw), WheelSpeed_LF (km/h×10), WheelSpeed_RF (km/h×10)
  Frame 5: WheelSpeed_LR (km/h×10), WheelSpeed_RR (km/h×10), (reserved)
  Frames 6–13: additional G5 channels (decoded when needed)

Usage:
    parser = G5GenericDashParser()           # default CAN ID 0x3E8
    parser.feed(msg.arbitration_id, msg.data)
    rpm = parser.rpm                         # None until frame 0 received
"""

from __future__ import annotations

import struct
import time
from typing import Optional

_STOMP_BYTES = struct.Struct("<hhh")  # three LE signed int16

# Frame indices
_FRAME_RPM_MAP_TPS = 0
_FRAME_CLT_IAT_LAMBDA = 1
_FRAME_OIL_FUEL = 2
_FRAME_BATT_INJ_ETHANOL = 3
_FRAME_GEAR_WHEEL_LF_RF = 4
_FRAME_WHEEL_LR_RR = 5

_FRAME_COUNT = 14  # total valid frame indices (0–13)
_MSG_LEN = 8       # all Generic Dash frames are exactly 8 bytes
_BYTE1_RESERVED = 0x00

# Gasoline stoichiometric ratio for AFR conversion
_STOICH = 14.7


class G5GenericDashParser:
    """Stateful decoder for the Link G5 Generic Dash multiplexed CAN stream.

    Call feed() for every incoming CAN message. Properties return the
    decoded engineering value, or None if that sub-frame has not yet
    been received. is_stale() returns True if no frame has arrived
    within stale_timeout seconds.
    """

    def __init__(
        self,
        can_id: int = 0x3E8,
        stale_timeout: float = 1.0,
    ) -> None:
        self._can_id = can_id
        self._stale_timeout = stale_timeout
        # Raw int16 triplets keyed by frame index
        self._raw: dict[int, tuple[int, int, int]] = {}
        # Monotonic timestamps of last frame receipt per index
        self._ts: dict[int, float] = {}

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def feed(self, can_id: int, data: bytes | bytearray) -> bool:
        """Ingest a CAN frame.

        Returns True if the frame was accepted (correct ID, correct
        length, valid header bytes), False otherwise.
        """
        if can_id != self._can_id:
            return False
        if len(data) != _MSG_LEN:
            return False
        frame_idx = data[0]
        if data[1] != _BYTE1_RESERVED:
            return False
        if frame_idx >= _FRAME_COUNT:
            return False
        s0, s1, s2 = _STOMP_BYTES.unpack_from(data, 2)
        self._raw[frame_idx] = (s0, s1, s2)
        self._ts[frame_idx] = time.monotonic()
        return True

    def is_stale(self) -> bool:
        """True if no frame has arrived within stale_timeout seconds."""
        if not self._ts:
            return True
        return (time.monotonic() - max(self._ts.values())) > self._stale_timeout

    def reset(self) -> None:
        """Clear all stored frames and timestamps."""
        self._raw.clear()
        self._ts.clear()

    # ------------------------------------------------------------------
    # Frame 0: RPM, MAP, TPS
    # ------------------------------------------------------------------

    @property
    def rpm(self) -> Optional[float]:
        """Engine speed in RPM."""
        r = self._raw.get(_FRAME_RPM_MAP_TPS)
        return float(r[0]) if r is not None else None

    @property
    def map_kpa(self) -> Optional[float]:
        """Manifold absolute pressure in kPa."""
        r = self._raw.get(_FRAME_RPM_MAP_TPS)
        return r[1] * 0.1 if r is not None else None

    @property
    def tps_pct(self) -> Optional[float]:
        """Throttle position in percent (0–100)."""
        r = self._raw.get(_FRAME_RPM_MAP_TPS)
        return r[2] * 0.1 if r is not None else None

    # ------------------------------------------------------------------
    # Frame 1: CLT, IAT, Lambda1
    # ------------------------------------------------------------------

    @property
    def coolant_temp_c(self) -> Optional[float]:
        """Coolant temperature in °C."""
        r = self._raw.get(_FRAME_CLT_IAT_LAMBDA)
        return r[0] * 0.1 if r is not None else None

    @property
    def iat_c(self) -> Optional[float]:
        """Intake air temperature in °C."""
        r = self._raw.get(_FRAME_CLT_IAT_LAMBDA)
        return r[1] * 0.1 if r is not None else None

    @property
    def lambda1(self) -> Optional[float]:
        """Wideband lambda (λ). Stoichiometric = 1.000."""
        r = self._raw.get(_FRAME_CLT_IAT_LAMBDA)
        return r[2] * 0.001 if r is not None else None

    @property
    def lambda1_afr(self) -> Optional[float]:
        """Wideband AFR (gasoline stoich = 14.7)."""
        lam = self.lambda1
        return lam * _STOICH if lam is not None else None

    # ------------------------------------------------------------------
    # Frame 2: OilPress, OilTemp, FuelPress
    # ------------------------------------------------------------------

    @property
    def oil_pressure_kpa(self) -> Optional[float]:
        """Oil pressure in kPa."""
        r = self._raw.get(_FRAME_OIL_FUEL)
        return r[0] * 0.1 if r is not None else None

    @property
    def oil_temp_c(self) -> Optional[float]:
        """Oil temperature in °C."""
        r = self._raw.get(_FRAME_OIL_FUEL)
        return r[1] * 0.1 if r is not None else None

    @property
    def fuel_pressure_kpa(self) -> Optional[float]:
        """Fuel pressure in kPa."""
        r = self._raw.get(_FRAME_OIL_FUEL)
        return r[2] * 0.1 if r is not None else None

    # ------------------------------------------------------------------
    # Frame 3: Battery, InjDuty, Ethanol
    # ------------------------------------------------------------------

    @property
    def battery_v(self) -> Optional[float]:
        """Battery voltage in V."""
        r = self._raw.get(_FRAME_BATT_INJ_ETHANOL)
        return r[0] * 0.01 if r is not None else None

    @property
    def injector_duty_pct(self) -> Optional[float]:
        """Injector duty cycle in percent."""
        r = self._raw.get(_FRAME_BATT_INJ_ETHANOL)
        return r[1] * 0.1 if r is not None else None

    @property
    def ethanol_pct(self) -> Optional[float]:
        """Ethanol content in percent."""
        r = self._raw.get(_FRAME_BATT_INJ_ETHANOL)
        return r[2] * 0.1 if r is not None else None

    # ------------------------------------------------------------------
    # Frame 4: Gear, WheelSpeed LF, WheelSpeed RF
    # ------------------------------------------------------------------

    @property
    def gear(self) -> Optional[int]:
        """Current gear (0 = neutral)."""
        r = self._raw.get(_FRAME_GEAR_WHEEL_LF_RF)
        return int(r[0]) if r is not None else None

    @property
    def wheel_speed_lf_kph(self) -> Optional[float]:
        """Left-front wheel speed in km/h."""
        r = self._raw.get(_FRAME_GEAR_WHEEL_LF_RF)
        return r[1] * 0.1 if r is not None else None

    @property
    def wheel_speed_rf_kph(self) -> Optional[float]:
        """Right-front wheel speed in km/h."""
        r = self._raw.get(_FRAME_GEAR_WHEEL_LF_RF)
        return r[2] * 0.1 if r is not None else None

    # ------------------------------------------------------------------
    # Frame 5: WheelSpeed LR, WheelSpeed RR
    # ------------------------------------------------------------------

    @property
    def wheel_speed_lr_kph(self) -> Optional[float]:
        """Left-rear wheel speed in km/h."""
        r = self._raw.get(_FRAME_WHEEL_LR_RR)
        return r[0] * 0.1 if r is not None else None

    @property
    def wheel_speed_rr_kph(self) -> Optional[float]:
        """Right-rear wheel speed in km/h."""
        r = self._raw.get(_FRAME_WHEEL_LR_RR)
        return r[1] * 0.1 if r is not None else None
