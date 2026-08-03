"""Acquisition sources. SimSource and LabJackSource share one interface."""

import math
import os
import random
from collections import deque

HASS_ZERO_V = float(os.getenv("HASS_ZERO_V", "2.5"))
HASS_SENS_V_PER_A = float(os.getenv("HASS_SENS_V_PER_A", "0.0125"))
HASS_TURNS = int(os.getenv("HASS_TURNS", "1"))
LJTD_RATIO = float(os.getenv("LJTD_RATIO", "25.0"))
FLOW_LPM_PER_HZ = float(os.getenv("FLOW_LPM_PER_HZ", "0.307"))
FLOW_WINDOW_S = float(os.getenv("FLOW_WINDOW_S", "2.0"))

# UNVERIFIED. A wrong index yields a counter that never increments.
DIO_EF_COUNTER_INDEX = int(os.getenv("DIO_EF_COUNTER_INDEX", "9"))
DIO_EF_DEBOUNCE_US = float(os.getenv("DIO_EF_DEBOUNCE_US", "1500"))

COMPARATOR_WIRED = os.getenv("COMPARATOR_WIRED", "0") == "1"

# Match the bench: a two-channel LJTick on AIN2/AIN3 occupies AIN3.
CURRENT_AIN = int(os.getenv("CURRENT_AIN", "0"))
VOLTAGE_AIN = int(os.getenv("VOLTAGE_AIN", "2"))
THERMISTOR_AIN = int(os.getenv("THERMISTOR_AIN", "3"))

CURRENT_REDLINE_A = float(os.getenv("CURRENT_REDLINE_A", "11.0"))


def hass_amps(v_ain: float) -> float:
    return (v_ain - HASS_ZERO_V) / (HASS_SENS_V_PER_A * HASS_TURNS)


def ljtd_volts(v_ain: float) -> float:
    return v_ain * LJTD_RATIO


def flow_lpm(pulse_hz: float) -> float:
    return pulse_hz * FLOW_LPM_PER_HZ


class FlowWindow:
    """Rolling-window pulse rate"""

    def __init__(self, window_s: float = FLOW_WINDOW_S):
        self.window_s = window_s
        self._samples: deque[tuple[float, float]] = deque()

    def update(self, mono_s: float, count: float) -> float:
        self._samples.append((mono_s, count))
        while len(self._samples) > 2 and mono_s - self._samples[0][0] > self.window_s:
            self._samples.popleft()
        if len(self._samples) < 2:
            return 0.0
        t0, c0 = self._samples[0]
        t1, c1 = self._samples[-1]
        span = t1 - t0
        if span <= 0:
            return 0.0
        return max((c1 - c0) / span, 0.0)

    @property
    def span_s(self) -> float:
        if len(self._samples) < 2:
            return 0.0
        return self._samples[-1][0] - self._samples[0][0]


class SimSource:
    """Plausible fake data so the whole stack runs with no hardware"""

    def __init__(self, ramp_s: float = 4.0, thermal_tau_s: float = 1.2):
        self.level = 0.0
        self.enabled = False
        self.ramp_s = ramp_s
        self.thermal_tau_s = thermal_tau_s
        self._optical = 0.0
        self._temp = 22.0
        self._count = 0.0
        self._flow = FlowWindow()
        self._mono = 0.0
        self.interlock_forced_open = False

    def set_enable(self, on: bool):
        self.enabled = bool(on)

    def read(self, dt: float) -> dict:
        self._mono += dt
        target = 1.0 if self.enabled else 0.0
        slew = dt / self.ramp_s
        self.level = (min(target, self.level + slew) if self.level < target
                      else max(target, self.level - slew))

        lvl = self.level
        current = 10.23 * lvl + random.gauss(0, 0.02)
        voltage = (39.0 if lvl > 0.01 else 0.0) + random.gauss(0, 0.05)

        alpha = 1.0 - math.exp(-dt / self.thermal_tau_s) if dt > 0 else 0.0
        self._optical += alpha * (190.0 * lvl - self._optical)
        self._temp += alpha * ((22.0 + 6.0 * lvl) - self._temp)

        self._count += 16.0 * dt
        hz = self._flow.update(self._mono, self._count)

        return {
            "current_a": round(current, 4),
            "voltage_v": round(voltage, 4),
            "temp_c": round(self._temp + random.gauss(0, 0.05), 3),
            "flow_lpm": round(flow_lpm(hz), 3),
            "flow_hz": round(hz, 3),
            "interlock_closed": 0 if self.interlock_forced_open else int(self.enabled),
            "comparator_tripped": 0,
            "irradiance_frac": round(lvl, 4),
            "sim_optical_w": round(max(self._optical + random.gauss(0, 0.4), 0.0), 3),
        }

    def slow(self) -> dict:
        return {}

    def close(self):
        self.set_enable(False)


class LabJackSource:
    """Real T7 over Ethernet. USB would need device passthrough into Docker and"""

    def __init__(self, identifier: str | None = None):
        from labjack import ljm

        self._ljm = ljm
        ident = identifier or os.getenv("LABJACK_ID", "ANY")
        conn = os.getenv("LABJACK_CONN", "ETHERNET")
        self.handle = ljm.openS("T7", conn, ident)

        # Before anything else: makes a restart mid-run safe.
        ljm.eWriteName(self.handle, "DAC0", 0.0)

        self.i_ch = f"AIN{CURRENT_AIN}"
        self.v_ch = f"AIN{VOLTAGE_AIN}"
        self.t_ch = f"AIN{THERMISTOR_AIN}"

        self._names = [self.i_ch, self.v_ch, f"{self.t_ch}_EF_READ_A",
                       "FIO1", "DIO0_EF_READ_A"]
        if COMPARATOR_WIRED:
            self._names.append("FIO3")

        self._configure()
        self._flow = FlowWindow()
        self.read_errors = 0

    def _configure(self):
        names, values = [], []

        # HASS output rides on a 2.5 V offset.
        for ch in (self.i_ch, self.v_ch):
            names += [f"{ch}_RANGE", f"{ch}_RESOLUTION_INDEX", f"{ch}_NEGATIVE_CH"]
            values += [10.0, 8, 199]

        # Steinhart-Hart in firmware.
        t = self.t_ch
        names += [f"{t}_EF_INDEX", f"{t}_EF_CONFIG_A", f"{t}_EF_CONFIG_B",
                  f"{t}_EF_CONFIG_D", f"{t}_EF_CONFIG_E", f"{t}_EF_CONFIG_F"]
        values += [50, 1, 0, 1.0, 0.0, 10000.0]

        # PLACEHOLDERS. Run tools/calibrate_thermistor.py.
        names += [f"{t}_EF_CONFIG_G", f"{t}_EF_CONFIG_H",
                  f"{t}_EF_CONFIG_I", f"{t}_EF_CONFIG_J"]
        values += [float(os.getenv("SH_A", "0.001125")),
                   float(os.getenv("SH_B", "0.000234")),
                   float(os.getenv("SH_C", "0.0")),
                   float(os.getenv("SH_D", "0.0000000876"))]

        # Index writes are ignored while an EF is live.
        names += ["DIO0_EF_ENABLE", "DIO0_EF_INDEX",
                  "DIO0_EF_CONFIG_A", "DIO0_EF_ENABLE"]
        values += [0, DIO_EF_COUNTER_INDEX, DIO_EF_DEBOUNCE_US, 1]

        self._ljm.eWriteNames(self.handle, len(names), names, values)

    def set_enable(self, on: bool):
        """Raises the chain input only. Key, lid, and flow switches sit downstream in"""
        self._ljm.eWriteName(self.handle, "DAC0", 5.0 if on else 0.0)

    def read(self, dt: float) -> dict:
        import time
        # One scan, one timestamp.
        vals = self._ljm.eReadNames(self.handle, len(self._names), self._names)
        by_name = dict(zip(self._names, vals))

        hz = self._flow.update(time.monotonic(), by_name["DIO0_EF_READ_A"])
        ain0 = by_name[self.i_ch]
        ain2 = by_name[self.v_ch]

        out = {
            "current_a": round(hass_amps(ain0), 4),
            "voltage_v": round(ljtd_volts(ain2), 4),
            "temp_c": round(by_name[f"{self.t_ch}_EF_READ_A"], 3),
            "flow_lpm": round(flow_lpm(hz), 3),
            "flow_hz": round(hz, 3),
            "interlock_closed": 1 if by_name["FIO1"] > 0.5 else 0,
            "comparator_tripped": 0,
            "hass_raw_v": round(ain0, 6),
            "ljtd_raw_v": round(ain2, 6),
        }
        if COMPARATOR_WIRED:
            out["comparator_tripped"] = 1 if by_name["FIO3"] < 0.5 else 0
        return out

    def close(self):
        try:
            self.set_enable(False)
        finally:
            self._ljm.close(self.handle)


def make_source(kind: str):
    return LabJackSource() if kind == "labjack" else SimSource()
