"""Legacy Windows-side Ophir sender. Superseded by direct USB on the Pi."""

import argparse
import sys
import time

import requests


class ComBackend:
    """Windows-only, via Ophir's COM object. Requires StarLab installed (it registers"""

    def __init__(self, channel: int = 0):
        import win32com.client  # pywin32

        self.channel = channel
        self.com = win32com.client.Dispatch("OphirLMMeasurement.CoLMMeasurement")
        self.com.StopAllStreams()
        self.com.CloseAll()

        serials = self.com.ScanUSB()
        if not serials:
            raise RuntimeError("no Ophir USB device found")
        self.serial = serials[0]
        self.handle = self.com.OpenUSBDevice(self.serial)

        exists, _, _ = self.com.IsSensorExists(self.handle, self.channel)
        if not exists:
            raise RuntimeError(f"no sensor on channel {self.channel}")

        # Anchor before streaming: erring late produces negative ages.
        self.anchor_wall_ns = time.time_ns()
        self.anchor_mono_ns = time.monotonic_ns()
        self.com.StartStream(self.handle, self.channel)

    def read(self) -> list[tuple[int, float]]:
        """Drain whatever the meter has buffered"""
        values, timestamps, _statuses = self.com.GetData(self.handle, self.channel)
        out = []
        for v, t_ms in zip(values, timestamps):
            t_ns = self.anchor_wall_ns + int(float(t_ms) * 1_000_000)
            out.append((t_ns, float(v)))
        return out

    def close(self):
        try:
            self.com.StopAllStreams()
            self.com.CloseAll()
        except Exception:
            pass


class SerialBackend:
    """RS-232 command/response. Works from Linux, so this can run on the Pi itself"""

    def __init__(self, port: str, baud: int = 9600, cmd: str = "$SP", timeout: float = 0.5):
        import serial  # pyserial

        self.cmd = (cmd + "\r\n").encode()
        self.ser = serial.Serial(port, baud, timeout=timeout)
        time.sleep(0.2)
        self.ser.reset_input_buffer()

    def read(self) -> list[tuple[int, float]]:
        self.ser.write(self.cmd)
        # Stamp before parsing.
        line = self.ser.readline().decode(errors="ignore").strip()
        t_ns = time.time_ns()
        if not line:
            return []
        # Replies look like '* 1.234E+02'.
        token = line.lstrip("*").strip().split()[0] if line.lstrip("*").strip() else ""
        try:
            return [(t_ns, float(token))]
        except ValueError:
            return []

    def close(self):
        try:
            self.ser.close()
        except Exception:
            pass


class SimBackend:
    """Fake meter with a realistic thermal lag, so you can develop and test the bridge,"""

    def __init__(self, rate_hz: float = 12.0, tau_s: float = 1.2):
        self.period = 1.0 / rate_hz
        self.tau = tau_s
        self.value = 0.0
        self._next = time.monotonic()
        self._t0 = time.monotonic()

    def read(self) -> list[tuple[int, float]]:
        out = []
        now = time.monotonic()
        while self._next <= now:
            import math
            import random

            phase = ((now - self._t0) % 40.0) / 40.0
            target = 230.0 * (2 * phase if phase < 0.5 else 2 * (1 - phase))
            alpha = 1.0 - math.exp(-self.period / self.tau)
            self.value += alpha * (target - self.value)
            out.append((time.time_ns(), max(0.0, self.value + random.gauss(0, 0.5))))
            self._next += self.period
        return out

    def close(self):
        pass


def make_backend(args):
    if args.backend == "com":
        return ComBackend(channel=args.channel)
    if args.backend == "serial":
        if not args.port:
            sys.exit("--port is required for the serial backend")
        return SerialBackend(args.port, args.baud, args.cmd)
    return SimBackend(rate_hz=args.sim_hz)


def measure_offset(session: requests.Session, api: str) -> tuple[int, int] | None:
    """One NTP-style exchange against the API"""
    t1 = time.time_ns()
    try:
        r = session.post(f"{api}/sync/ping", json={"t1_ns": t1}, timeout=3.0)
        r.raise_for_status()
        d = r.json()
    except Exception as e:
        print(f"sync ping failed: {e}")
        return None
    t4 = time.time_ns()
    t2, t3 = int(d["t2_ns"]), int(d["t3_ns"])
    offset = ((t2 - t1) + (t3 - t4)) // 2
    rtt = (t4 - t1) - (t3 - t2)
    return offset, rtt


def main():
    p = argparse.ArgumentParser(description="Ophir -> stand API bridge")
    p.add_argument("--api", default="http://10.3.0.53:8000")
    p.add_argument("--backend", choices=["com", "serial", "sim"], default="sim")
    p.add_argument("--channel", type=int, default=0)
    p.add_argument("--port", help="serial port, e.g. /dev/ttyUSB0 or COM3")
    p.add_argument("--baud", type=int, default=9600)
    p.add_argument("--cmd", default="$SP", help="RS232 power query (VERIFY in manual)")
    p.add_argument("--sim-hz", type=float, default=12.0)
    p.add_argument("--post-hz", type=float, default=4.0,
                   help="how often to POST batches (batching cuts round trips)")
    p.add_argument("--sync-every-s", type=float, default=10.0)
    args = p.parse_args()

    backend = make_backend(args)
    session = requests.Session()   # reuses the TCP connection, lower latency variance

    # Prime the offset before shipping data.
    print("measuring clock offset...")
    for _ in range(5):
        res = measure_offset(session, args.api)
        if res:
            offset, rtt = res
            try:
                session.post(f"{args.api}/sync/report",
                             json={"offset_ns": offset, "round_trip_ns": rtt},
                             timeout=3.0)
            except Exception as e:
                print(f"sync report failed: {e}")
            print(f"  offset {offset/1e6:+.3f} ms   rtt {rtt/1e6:.3f} ms")
        time.sleep(0.2)

    post_period = 1.0 / args.post_hz
    next_post = time.monotonic()
    next_sync = time.monotonic() + args.sync_every_s
    pending: list[tuple[int, float]] = []
    sent = 0

    print(f"streaming to {args.api}  (backend={args.backend})   Ctrl+C to stop")
    try:
        while True:
            pending.extend(backend.read())
            now = time.monotonic()

            if now >= next_post and pending:
                payload = {
                    "device": f"ophir-{args.backend}",
                    "samples": [{"t_bridge_ns": t, "power_w": v} for t, v in pending],
                }
                try:
                    r = session.post(f"{args.api}/ingest/optical", json=payload, timeout=5.0)
                    r.raise_for_status()
                    sent += len(pending)
                    pending.clear()
                    print(f"\rsent {sent} samples", end="", flush=True)
                except Exception as e:
                    # Buffer and retry, capped.
                    print(f"\npost failed, buffering ({len(pending)}): {e}")
                    pending = pending[-5000:]
                next_post = now + post_period

            # Clocks drift.
            if now >= next_sync:
                res = measure_offset(session, args.api)
                if res:
                    offset, rtt = res
                    try:
                        session.post(f"{args.api}/sync/report",
                                     json={"offset_ns": offset, "round_trip_ns": rtt},
                                     timeout=3.0)
                    except Exception:
                        pass
                next_sync = now + args.sync_every_s

            time.sleep(0.01)
    except KeyboardInterrupt:
        print("\nstopping")
    finally:
        backend.close()


if __name__ == "__main__":
    main()
