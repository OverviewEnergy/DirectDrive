"""Monotonic-anchored absolute timestamps."""

import time


class Clock:
    """Monotonic-anchored absolute clock. One instance per process."""

    def __init__(self):
        self.re_anchor()

    def re_anchor(self):
        """Re-tie the monotonic clock to the current wall clock. Do this BETWEEN runs."""
        self._mono0 = time.monotonic_ns()
        self._wall0 = time.time_ns()

    def now_ns(self) -> int:
        """Absolute timestamp in nanoseconds since epoch. Never steps."""
        return self._wall0 + (time.monotonic_ns() - self._mono0)

    def now_s(self) -> float:
        return self.now_ns() / 1e9

    @staticmethod
    def mono_ns() -> int:
        """Raw monotonic, for measuring durations only."""
        return time.monotonic_ns()

    def drift_vs_wall_ns(self) -> int:
        """How far our anchored clock has diverged from the OS wall clock"""
        return self.now_ns() - time.time_ns()


# Process-wide singleton.
CLOCK = Clock()
