"""Ophir readers. Local backends share the LabJack process and clock."""

import math
import os
import random
import threading
import time

from clock import CLOCK


class SerialOphir:
    """RS-232 command/response reader"""

    def __init__(self, port: str, baud: int = 9600, cmd: str = "$SP", timeout: float = 0.5):
        import serial  # pyserial

        self.cmd = (cmd + "\r\n").encode()
        self.ser = serial.Serial(port, baud, timeout=timeout)
        time.sleep(0.2)
        self.ser.reset_input_buffer()

    def read_one(self) -> tuple[int, float] | None:
        self.ser.write(self.cmd)
        line = self.ser.readline().decode(errors="ignore").strip()
        # Stamp closest to the measurement.
        ts = CLOCK.now_ns()
        if not line:
            return None
        body = line.lstrip("*").strip()
        if not body:
            return None
        try:
            return ts, float(body.split()[0])
        except ValueError:
            return None

    def close(self):
        try:
            self.ser.close()
        except Exception:
            pass


class UsbLinuxOphir:
    """Direct pyusb driver for Ophir meters on Linux. No vendor driver, no Windows"""

    VENDOR_ID = 0x0BD3
    PRODUCT_IDS = {
        "juno": 0x0778, "junoplus": 0x0778, "pm841": 0x0778, "pm844": 0x0778,
        "nova2": 0x0777, "vega": 0x0777,
        "starlite": 0x0779, "starbright": 0x0779, "centauri": 0x0779,
    }
    # (start, stop) per product family
    STREAM_CMDS = {0x0778: ("CS 3", "CS 1"),
                   0x0777: ("CS 1 1 3", "CS 0"),
                   0x0779: ("CS 2", "CS 1")}

    def __init__(self, channel: int = 0, model: str = "juno", timeout_ms: int = 2000):
        import usb.core
        import usb.util

        self._usb = usb.util
        self.channel = channel
        self.timeout_ms = timeout_ms
        self.pid = self.PRODUCT_IDS.get(model.lower())
        if self.pid is None:
            raise ValueError(f"unknown Ophir model {model!r}, "
                             f"expected one of {sorted(self.PRODUCT_IDS)}")

        self.dev = usb.core.find(idVendor=self.VENDOR_ID, idProduct=self.pid)
        if self.dev is None:
            raise RuntimeError(
                f"no Ophir device at VID 0x{self.VENDOR_ID:04X} "
                f"PID 0x{self.pid:04X}. Check lsusb, the cable, and that the "
                f"udev rule is installed and the device replugged since."
            )

        self.dev.set_configuration(1)
        try:
            self.dev.detach_kernel_driver(0)
        except Exception:
            pass
        usb.util.claim_interface(self.dev, 0)

        # Fail loudly here rather than returning None on every read.
        if self._cmd("FP") is None:
            raise RuntimeError("Ophir did not answer the FP probe. Device present "
                               "but not responding. Is StarLab or another process "
                               "holding it?")

        start, self._stop_cmd = self.STREAM_CMDS[self.pid]
        self._cmd(start)

    def _cmd(self, command: str) -> str | None:
        try:
            self.dev.ctrl_transfer(0x40, 0x02, 0, 0,
                                   f"${command}\r\n".encode(), self.timeout_ms)
            raw = self.dev.ctrl_transfer(0xC0, 0x04, 0, 0, 64, self.timeout_ms)
        except Exception:
            return None
        if not raw:
            return None
        text = bytes(raw).decode("utf-8", "replace").strip()
        return text or None

    def read_one(self) -> tuple[int, float] | None:
        reply = self._cmd("SP")
        if reply in (None, "?UC"):
            reply = self._cmd("MM")
        # Stamp before parsing.
        ts_ns = CLOCK.now_ns()
        if not reply or reply[0] not in "*?":
            return None
        try:
            return ts_ns, float(reply[1:])
        except ValueError:
            return None

    def close(self):
        try:
            self._cmd(self._stop_cmd)
        finally:
            try:
                self._usb.release_interface(self.dev, 0)
                self._usb.dispose_resources(self.dev)
            except Exception:
                pass


class SimOphir:
    """Fake FL400A. First-order thermal lag on purpose, because that lag is the dominant"""

    def __init__(self, tau_s: float = 1.5, noise_w: float = 0.4):
        self.tau_s = tau_s
        self.noise_w = noise_w
        self.value = 0.0
        self._last = time.monotonic()
        self._get_target = lambda: 0.0   # main.py injects the real drive level

    def set_target_source(self, fn):
        """Let the simulator follow the simulated drive level for a coherent picture."""
        self._get_target = fn

    def read_one(self) -> tuple[int, float] | None:
        now = time.monotonic()
        dt = now - self._last
        self._last = now
        target = 230.0 * float(self._get_target())
        alpha = 1.0 - math.exp(-dt / self.tau_s) if dt > 0 else 0.0
        self.value += alpha * (target - self.value)
        return CLOCK.now_ns(), max(0.0, self.value + random.gauss(0, self.noise_w))

    def close(self):
        pass


def make_ophir(backend: str):
    if backend == "serial":
        port = os.getenv("OPHIR_PORT")
        if not port:
            raise ValueError("OPHIR_PORT must be set for the serial backend")
        return SerialOphir(
            port,
            baud=int(os.getenv("OPHIR_BAUD", "9600")),
            cmd=os.getenv("OPHIR_CMD", "$SP"),
        )
    if backend == "usb_linux":
        return UsbLinuxOphir(channel=int(os.getenv("OPHIR_CHANNEL", "0")),
                             model=os.getenv("OPHIR_MODEL", "juno"))
    if backend == "sim":
        return SimOphir(tau_s=float(os.getenv("OPHIR_TAU_S", "1.5")))
    raise ValueError(f"unknown Ophir backend: {backend}")


class OphirReader:
    """Background thread that polls the meter and pushes into a shared OpticalStream"""

    def __init__(self, stream, backend: str, rate_hz: float = 12.0):
        self.stream = stream
        self.backend_name = backend
        self.period = 1.0 / rate_hz
        self.device = None
        self._thread = None
        self._stop = threading.Event()
        self.errors = 0
        self.reads = 0
        self.last_error = ""

    def start(self):
        self.device = make_ophir(self.backend_name)
        # Same-process clock: offset is zero by construction, not unmeasured.
        self.stream.sync.add(0, 0)
        self._thread = threading.Thread(target=self._run, daemon=True, name="ophir")
        self._thread.start()
        return self.device

    def _run(self):
        while not self._stop.is_set():
            t0 = time.monotonic()
            try:
                got = self.device.read_one()
                if got is not None:
                    ts, watts = got
                    self.stream.push_external(ts, watts)
                    self.reads += 1
            except Exception as e:
                self.errors += 1
                self.last_error = str(e)
            elapsed = time.monotonic() - t0
            self._stop.wait(max(0.0, self.period - elapsed))

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        if self.device is not None:
            self.device.close()

    def stats(self) -> dict:
        return {
            "backend": self.backend_name,
            "reads": self.reads,
            "errors": self.errors,
            "last_error": self.last_error,
            "rate_hz": round(1.0 / self.period, 2),
        }
