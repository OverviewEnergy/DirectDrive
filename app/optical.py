"""Optical power stream: ingest, clock alignment, interpolation."""

import bisect
import statistics
from collections import deque


def offset_from_exchange(t1_ns: int, t2_ns: int, t3_ns: int, t4_ns: int) -> tuple[int, int]:
    """NTP's four-timestamp clock comparison. Same math your lab's time server uses"""
    offset = ((t2_ns - t1_ns) + (t3_ns - t4_ns)) // 2
    round_trip = (t4_ns - t1_ns) - (t3_ns - t2_ns)
    return offset, round_trip


class ClockSync:
    """Tracks the bridge->server clock offset from repeated exchanges"""

    def __init__(self, window: int = 9):
        self._offsets = deque(maxlen=window)
        self._rtts = deque(maxlen=window)
        self.samples = 0

    def add(self, offset_ns: int, round_trip_ns: int):
        self._offsets.append(offset_ns)
        self._rtts.append(round_trip_ns)
        self.samples += 1

    @property
    def offset_ns(self) -> int:
        """Best estimate of server_clock - bridge_clock. Zero if never measured."""
        if not self._offsets:
            return 0
        return int(statistics.median(self._offsets))

    @property
    def rtt_ns(self) -> int:
        if not self._rtts:
            return 0
        return int(statistics.median(self._rtts))

    @property
    def uncertainty_ns(self) -> int:
        """Half the round-trip time: the irreducible ambiguity about where in the"""
        return self.rtt_ns // 2

    def stats(self) -> dict:
        return {
            "offset_ms": self.offset_ns / 1e6,
            "rtt_ms": self.rtt_ns / 1e6,
            "uncertainty_ms": self.uncertainty_ns / 1e6,
            "exchanges": self.samples,
        }


class OpticalStream:
    """Ring buffer of (timestamp, power) already converted to SERVER time"""

    def __init__(self, maxlen: int = 20000, stale_after_s: float = 2.0):
        self._ts: deque[int] = deque(maxlen=maxlen)      # server-time ns, ascending
        self._val: deque[float] = deque(maxlen=maxlen)
        self.stale_after_s = stale_after_s
        self.sync = ClockSync()
        self.received = 0
        self.rejected_out_of_order = 0
        # Lets the simulator stand down automatically.
        self.external_samples = 0

    def push(self, server_ts_ns: int, power_w: float) -> bool:
        """Add one sample, already on server time. Returns False if it arrived out of"""
        if self._ts and server_ts_ns <= self._ts[-1]:
            self.rejected_out_of_order += 1
            return False
        self._ts.append(server_ts_ns)
        self._val.append(float(power_w))
        self.received += 1
        return True

    def push_external(self, server_ts_ns: int, power_w: float) -> bool:
        """Add a sample that came from a real bridge, not the simulator."""
        self.external_samples += 1
        return self.push(server_ts_ns, power_w)

    def push_bridge_time(self, bridge_ts_ns: int, power_w: float) -> bool:
        """Add a sample stamped on the BRIDGE clock; converts using the measured offset."""
        return self.push_external(bridge_ts_ns + self.sync.offset_ns, power_w)

    def latest(self, now_ns: int) -> tuple[float | None, float | None]:
        """Newest value and its age in seconds. For live display only"""
        if not self._ts:
            return None, None
        age_s = (now_ns - self._ts[-1]) / 1e9
        return self._val[-1], age_s

    def interpolate_at(
        self, t_ns: int, max_gap_s: float | None = None
    ) -> float | None:
        """Linearly interpolate optical power at time t_ns"""
        n = len(self._ts)
        if n == 0:
            return None
        if t_ns < self._ts[0] or t_ns > self._ts[-1]:
            return None

        gap_limit_ns = None if max_gap_s is None else int(max_gap_s * 1e9)

        # Cheaper than copying the deque to a list every call.
        i = bisect.bisect_left(self._ts, t_ns)
        if i < n and self._ts[i] == t_ns:
            return self._val[i]

        lo, hi = i - 1, i
        t_lo, t_hi = self._ts[lo], self._ts[hi]
        if gap_limit_ns is not None and (t_hi - t_lo) > gap_limit_ns:
            return None

        span = t_hi - t_lo
        if span == 0:
            return self._val[lo]
        frac = (t_ns - t_lo) / span
        return self._val[lo] + frac * (self._val[hi] - self._val[lo])

    def stats(self) -> dict:
        return {
            "buffered": len(self._ts),
            "received": self.received,
            "external_samples": self.external_samples,
            "rejected_out_of_order": self.rejected_out_of_order,
            "sync": self.sync.stats(),
        }


def cross_correlate_lag(
    a_ts_ns: list[int], a_val: list[float],
    b_ts_ns: list[int], b_val: list[float],
    max_lag_s: float = 5.0, step_s: float = 0.01,
) -> tuple[float, float]:
    """Measure the true end-to-end lag between two signals that share a physical event"""
    if len(a_ts_ns) < 3 or len(b_ts_ns) < 3:
        return 0.0, 0.0

    # Zero mean, unit scale: amps vs watts must not dominate.
    def norm(v: list[float]) -> list[float]:
        m = sum(v) / len(v)
        c = [x - m for x in v]
        s = (sum(x * x for x in c) / len(c)) ** 0.5
        return [x / s for x in c] if s > 0 else c

    b_stream = OpticalStream(maxlen=len(b_ts_ns) + 1)
    for t, v in zip(b_ts_ns, b_val):
        b_stream.push(t, v)

    best_lag, best_corr = 0.0, -2.0
    steps = int(max_lag_s / step_s)

    for k in range(-steps, steps + 1):
        lag_s = k * step_s
        shift_ns = int(lag_s * 1e9)

        pairs_a, pairs_b = [], []
        for t, av in zip(a_ts_ns, a_val):
            bv = b_stream.interpolate_at(t + shift_ns)
            if bv is not None:
                pairs_a.append(av)
                pairs_b.append(bv)
        if len(pairs_b) < 3:
            continue

        # Normalize over the matched subset, or the result exceeds 1 and stops
        # being comparable across lags.
        corr = sum(x * y for x, y in zip(norm(pairs_a), norm(pairs_b))) / len(pairs_a)
        if corr > best_corr:
            best_corr, best_lag = corr, lag_s

    return best_lag, best_corr
