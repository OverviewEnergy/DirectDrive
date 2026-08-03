"""Control and acquisition service."""

import asyncio
import contextlib
import os
import time
import uuid
from enum import Enum
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from clock import CLOCK
from daq import CURRENT_REDLINE_A, make_source
from influx import InfluxClient
from onewire import OneWireBus
from ophir import OphirReader
from optical import OpticalStream, cross_correlate_lag, offset_from_exchange

MODE = os.getenv("MODE", "direct_drive")
SOURCE_KIND = os.getenv("SOURCE", "sim")
SAMPLE_HZ = float(os.getenv("SAMPLE_HZ", "20"))
STAND_ID = os.getenv("STAND_ID", "stand-1")

INFLUX_URL = os.getenv("INFLUX_URL", "http://influxdb:8086")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "dev-token")
INFLUX_ORG = os.getenv("INFLUX_ORG", "leolaser")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "telemetry")

# none = optical arrives over HTTP from a bridge. Otherwise read locally.
OPHIR_BACKEND = os.getenv("OPHIR_BACKEND", "none")
OPHIR_RATE_HZ = float(os.getenv("OPHIR_RATE_HZ", "12"))

TEMP_LIMIT_C = float(os.getenv("TEMP_LIMIT_C", "30.0"))
FLOW_MIN_LPM = float(os.getenv("FLOW_MIN_LPM", "2.0"))

# Node X is DAC0 through the switches, so the chain is only observable
# once the gate is up. Confirm within this window after enable.
INTERLOCK_CONFIRM_S = float(os.getenv("INTERLOCK_CONFIRM_S", "0.6"))

STATIC_DIR = Path(__file__).parent / "static"


class State(str, Enum):
    IDLE = "IDLE"
    ARMED = "ARMED"
    ENABLED = "ENABLED"
    STOPPED = "STOPPED"
    FAULT = "FAULT"


class Stand:
    def __init__(self):
        self.state = State.IDLE
        self.run_id: str | None = None
        self.run_started_ns: int | None = None
        self.enabled_mono: float | None = None
        self.latest: dict = {}
        self.fault_reason: str | None = None
        self.events: list[dict] = []
        self.subscribers: set[asyncio.Queue] = set()
        self.source = None
        self.ophir: OphirReader | None = None
        self.onewire: OneWireBus | None = None
        self.influx: InfluxClient | None = None
        self.optical = OpticalStream()
        self.loop_dt_s = 0.0
        self.loop_overruns = 0
        self.source_errors = 0

    def tags(self) -> dict:
        return {"stand": STAND_ID, "mode": MODE, "state": self.state.value,
                "run_id": self.run_id or "none"}

    def publish(self, payload: dict):
        for q in list(self.subscribers):
            if q.full():
                with contextlib.suppress(asyncio.QueueEmpty):
                    q.get_nowait()
            with contextlib.suppress(asyncio.QueueFull):
                q.put_nowait(payload)


STAND = Stand()
app = FastAPI(title="LEOLaser direct-drive stand")


def log_event(name: str, detail: str = ""):
    event = {"ts_ns": CLOCK.now_ns(), "name": name, "detail": detail}
    STAND.events.append(event)
    del STAND.events[:-200]
    if STAND.influx:
        STAND.influx.write("events", STAND.tags(),
                           {"name": name, "detail": detail or "-"}, event["ts_ns"])
    STAND.publish({"type": "event", **event})


def set_enable(on: bool):
    if STAND.source:
        STAND.source.set_enable(on)


def trip(reason: str):
    set_enable(False)
    STAND.enabled_mono = None
    STAND.state = State.FAULT
    STAND.fault_reason = reason
    log_event("fault", reason)


def check_limits(sample: dict):
    if STAND.state is not State.ENABLED:
        return
    if sample.get("comparator_tripped"):
        return trip("hardware comparator trip")
    if sample.get("current_a", 0.0) > CURRENT_REDLINE_A:
        return trip(f"current {sample['current_a']:.2f} A over redline "
                    f"{CURRENT_REDLINE_A:.2f} A")
    if sample.get("temp_c", 0.0) > TEMP_LIMIT_C:
        return trip(f"temperature {sample['temp_c']:.1f} C over limit "
                    f"{TEMP_LIMIT_C:.1f} C")
    if sample.get("flow_lpm", 99.0) < FLOW_MIN_LPM:
        return trip(f"flow {sample['flow_lpm']:.2f} LPM under minimum "
                    f"{FLOW_MIN_LPM:.2f} LPM")

    if not sample.get("interlock_closed"):
        settled = (STAND.enabled_mono is not None
                   and time.monotonic() - STAND.enabled_mono > INTERLOCK_CONFIRM_S)
        if settled:
            return trip("interlock chain open: a switch is open, or the chain "
                        "never closed after enable")


async def acquisition_loop():
    period = 1.0 / SAMPLE_HZ
    last = time.monotonic()
    next_tick = last

    while True:
        next_tick += period
        sleep_for = next_tick - time.monotonic()
        if sleep_for < 0:
            STAND.loop_overruns += 1
            next_tick = time.monotonic()
        else:
            await asyncio.sleep(sleep_for)

        now_mono = time.monotonic()
        dt = now_mono - last
        last = now_mono
        STAND.loop_dt_s = round(dt, 5)
        ts_ns = CLOCK.now_ns()

        try:
            sample = STAND.source.read(dt)
        except Exception as exc:
            STAND.source_errors += 1
            if STAND.state is State.ENABLED:
                trip(f"acquisition failure: {exc}")
            continue

        if STAND.onewire:
            sample.update(STAND.onewire.snapshot())

        current = sample.get("current_a", 0.0)
        voltage = sample.get("voltage_v", 0.0)
        sample["power_w"] = round(current * voltage, 3)
        sample["resistance_ohm"] = round(voltage / current, 4) if abs(current) > 0.05 else None

        # Simulator stands down once anything real is feeding us.
        sim_optical = sample.pop("sim_optical_w", None)
        if (sim_optical is not None and STAND.optical.external_samples == 0
                and STAND.ophir is None):
            STAND.optical.push(ts_ns, sim_optical)

        optical_w, optical_age = STAND.optical.latest(ts_ns)
        sample["optical_w"] = optical_w
        sample["optical_age_s"] = round(optical_age, 3) if optical_age is not None else None
        if optical_w is not None and sample["power_w"] > 1.0:
            sample["efficiency_pct"] = round(100.0 * optical_w / sample["power_w"], 2)

        check_limits(sample)

        sample["state"] = STAND.state.value
        sample["run_id"] = STAND.run_id
        sample["ts_ns"] = ts_ns
        sample["loop_dt_s"] = STAND.loop_dt_s
        STAND.latest = sample

        if STAND.influx and STAND.run_id:
            fields = {k: v for k, v in sample.items()
                      if isinstance(v, (int, float)) and k != "ts_ns"}
            STAND.influx.write("telemetry", STAND.tags(), fields, ts_ns)
            with contextlib.suppress(Exception):
                await STAND.influx.flush_if_due()

        STAND.publish({"type": "sample", **sample})


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI):
    STAND.source = make_source(SOURCE_KIND)
    set_enable(False)
    STAND.onewire = OneWireBus(STAND.source)
    STAND.influx = InfluxClient(INFLUX_URL, INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET)
    await STAND.influx.open()

    if OPHIR_BACKEND != "none":
        try:
            STAND.ophir = OphirReader(STAND.optical, OPHIR_BACKEND,
                                      rate_hz=OPHIR_RATE_HZ)
            STAND.ophir.start()
            log_event("ophir_local", f"backend={OPHIR_BACKEND} hz={OPHIR_RATE_HZ:g}")
        except Exception as exc:
            STAND.ophir = None
            log_event("ophir_failed", str(exc))

    tasks = [asyncio.create_task(acquisition_loop())]
    if STAND.onewire.enabled:
        tasks.append(asyncio.create_task(STAND.onewire.run()))
    log_event("service_start", f"mode={MODE} source={SOURCE_KIND} hz={SAMPLE_HZ:g}")

    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        if STAND.ophir:
            with contextlib.suppress(Exception):
                STAND.ophir.stop()
        with contextlib.suppress(Exception):
            set_enable(False)
            STAND.source.close()
        with contextlib.suppress(Exception):
            await STAND.influx.flush()
            await STAND.influx.close()


app.router.lifespan_context = lifespan


class OpticalSample(BaseModel):
    ts_ns: int
    power_w: float


class OpticalBatch(BaseModel):
    samples: list[OpticalSample]
    clock: str = Field("bridge", pattern="^(bridge|server)$")


class SyncRequest(BaseModel):
    t1_ns: int


class SyncReport(BaseModel):
    t1_ns: int
    t2_ns: int
    t3_ns: int
    t4_ns: int


def require(*states: State):
    if STAND.state not in states:
        raise HTTPException(409, f"state is {STAND.state.value}, "
                                f"expected one of {[s.value for s in states]}")


@app.get("/status")
def status():
    return {"state": STAND.state.value, "mode": MODE, "source": SOURCE_KIND,
            "run_id": STAND.run_id, "fault_reason": STAND.fault_reason,
            "redline_a": CURRENT_REDLINE_A, "temp_limit_c": TEMP_LIMIT_C,
            "flow_min_lpm": FLOW_MIN_LPM, "sample_hz": SAMPLE_HZ,
            "latest": STAND.latest, "events": STAND.events[-25:]}


@app.get("/latest")
def latest():
    return STAND.latest


@app.get("/health")
async def health():
    influx_ok = False
    with contextlib.suppress(Exception):
        influx_ok = await STAND.influx.ping()
    return {
        "state": STAND.state.value,
        "influx_reachable": influx_ok,
        "points_written": STAND.influx.points_written,
        "write_errors": STAND.influx.write_errors,
        "pending": STAND.influx.pending,
        "loop_dt_s": STAND.loop_dt_s,
        "loop_overruns": STAND.loop_overruns,
        "source_errors": STAND.source_errors,
        "onewire_enabled": bool(STAND.onewire and STAND.onewire.enabled),
        "onewire_errors": STAND.onewire.errors if STAND.onewire else 0,
        "optical": STAND.optical.stats(),
        "ophir_local": STAND.ophir.stats() if STAND.ophir else None,
        "ophir_backend": OPHIR_BACKEND,
        "clock_drift_vs_wall_ns": CLOCK.drift_vs_wall_ns(),
        "subscribers": len(STAND.subscribers),
    }


@app.post("/arm")
def arm():
    require(State.IDLE)
    STAND.state = State.ARMED
    STAND.fault_reason = None
    log_event("arm")
    return status()


@app.post("/enable")
def enable():
    require(State.ARMED)
    current = STAND.latest.get("current_a")
    if current is not None and abs(current) > 0.10:
        raise HTTPException(409, f"current is {current:.2f} A, not zero. Close the "
                                 f"shade before enabling: the SSR must never make "
                                 f"a live load")
    STAND.run_id = uuid.uuid4().hex[:12]
    STAND.run_started_ns = CLOCK.now_ns()
    STAND.enabled_mono = time.monotonic()
    STAND.state = State.ENABLED
    set_enable(True)
    log_event("enable", f"run_id={STAND.run_id}")
    return status()


@app.post("/stop")
def stop():
    require(State.ARMED, State.ENABLED)
    set_enable(False)
    STAND.enabled_mono = None
    STAND.state = State.STOPPED
    log_event("stop")
    return status()


@app.post("/estop")
def estop():
    set_enable(False)
    STAND.enabled_mono = None
    STAND.state = State.FAULT
    STAND.fault_reason = "operator e-stop"
    log_event("estop")
    return status()


@app.post("/reset")
def reset():
    require(State.STOPPED, State.FAULT)
    set_enable(False)
    STAND.state = State.IDLE
    STAND.enabled_mono = None
    STAND.run_id = None
    STAND.fault_reason = None
    CLOCK.re_anchor()
    log_event("reset")
    return status()


@app.post("/marker")
def marker(label: str = "marker"):
    log_event("marker", label)
    return {"ok": True, "label": label, "ts_ns": CLOCK.now_ns()}


@app.post("/sync/ping")
def sync_ping(req: SyncRequest):
    t2 = CLOCK.now_ns()
    return {"t1_ns": req.t1_ns, "t2_ns": t2, "t3_ns": CLOCK.now_ns()}


@app.post("/sync/report")
def sync_report(rep: SyncReport):
    offset_ns, rtt_ns = offset_from_exchange(rep.t1_ns, rep.t2_ns, rep.t3_ns, rep.t4_ns)
    STAND.optical.sync.add(offset_ns, rtt_ns)
    return STAND.optical.sync.stats()


@app.post("/ingest/optical")
def ingest_optical(batch: OpticalBatch):
    accepted = 0
    for sample in batch.samples:
        ok = (STAND.optical.push_external(sample.ts_ns, sample.power_w)
              if batch.clock == "server"
              else STAND.optical.push_bridge_time(sample.ts_ns, sample.power_w))
        accepted += bool(ok)
    return {"accepted": accepted, "received": len(batch.samples),
            "rejected_out_of_order": STAND.optical.rejected_out_of_order}


@app.post("/sim/interlock")
def sim_interlock(closed: bool = True):
    """Force the simulated chain open to exercise the fault path. Sim only."""
    if SOURCE_KIND != "sim":
        raise HTTPException(404, "simulator only")
    STAND.source.interlock_forced_open = not closed
    log_event("sim_interlock", "closed" if closed else "forced open")
    return {"interlock_closed": closed}


@app.get("/analysis/lag")
def analysis_lag(window_s: float = 30.0, max_lag_s: float = 3.0):
    lag = cross_correlate_lag(STAND.optical, window_s=window_s, max_lag_s=max_lag_s)
    return {"lag_s": lag, "window_s": window_s}


@app.websocket("/stream")
async def stream(ws: WebSocket):
    await ws.accept()
    queue: asyncio.Queue = asyncio.Queue(maxsize=120)
    STAND.subscribers.add(queue)
    try:
        await ws.send_json({"type": "hello", **status()})
        while True:
            await ws.send_json(await queue.get())
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        STAND.subscribers.discard(queue)


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")
