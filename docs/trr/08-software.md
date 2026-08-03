# 8. Software and Data Acquisition

## 8.1 Architecture

Both instruments attach to the Raspberry Pi 5 by USB. The Pi runs the control service, the
time-series database, and the visualisation server. Operator access is over a network
connection to a browser; no software is installed on the operator's machine.

```
   LabJack T7 ──────USB──────▶┐
                              │   Raspberry Pi 5
   Ophir Juno ──────USB──────▶┤     leolaser-api   :8000   control + acquisition
   + FL400A-BB-50             │     influxdb       :8086   time-series storage
                              │     grafana        :3000   analysis dashboards
                              └────────────┬───────────────
                                           │  WiFi, Pi in access point mode
                                           ▼
                                  Operator laptop, browser only
```

The Pi is the server. USB is the instrument transport, nothing more: the T7 presents as a
USB device driven through LabJack's LJM library, and the Juno presents as a vendor-specific
USB device driven by direct control transfers.

**No external network is required.** The Pi hosts its own WiFi access point and supplies
DHCP to clients. There is no router, no internet, and no dependency on site infrastructure.

## 8.2 Instrument connections

| Instrument | Transport | Driver | Rate |
|---|---|---|---|
| LabJack T7 | USB | LabJack LJM, native library plus Python binding | 20 Hz, all channels in one batched scan |
| Ophir Juno + FL400A-BB-50 | USB | Direct pyusb control transfers, VID 0x0BD3, PID 0x0778 | 12 Hz, separate thread |

Each instrument is opened exclusively by the control service. Only one process may hold a
given device, so the diagnostic tools in §8.9 require the service to be stopped first.

### 8.2.1 Ophir USB protocol

The Juno is driven without vendor software. Commands are ASCII, wrapped `$<CMD>\r\n`, sent
as vendor-specific control transfers:

| Direction | bmRequestType | bRequest |
|---|---|---|
| Host to device, command | 0x40 | 0x02 |
| Device to host, response | 0xC0 | 0x04 |

Responses are prefixed `*` on success or `?` on error. Streaming is started with `CS 3` and
stopped with `CS 1`. Power is read with `SP`, falling back to `MM`.

A udev rule granting non-root access to vendor 0x0bd3 is required; the meter must be
replugged after the rule is installed.

## 8.3 Services

All three run on the Pi and start automatically at boot.

| Service | Port | Runs as | Function |
|---|---|---|---|
| `leolaser-api` | 8000 | systemd unit, native | Instrument I/O, state machine, software interlocks, control panel |
| `influxdb` | 8086 | Docker container | Time-series storage, per-run records |
| `grafana` | 3000 | Docker container | Dashboards, annotations, post-run analysis |

The control service runs natively rather than in a container so it can reach USB devices
without device passthrough or in-container udev rules. The two data services are
containerised; neither touches hardware.

Container images are cached locally before deployment. Nothing is fetched at run time.

## 8.4 Operator access

| URL | Function |
|---|---|
| `http://<pi>:8000/` | Control panel. Arm, Enable, Stop, E-stop, Mark, Reset. Live telemetry |
| `http://<pi>:3000/` | Grafana. Historical data, run comparison, event annotations |
| `http://<pi>:8000/health` | Instrument and service health. Checked before every run |

The control panel is served by the Pi and requires only a browser. It has no external
dependencies, no content delivery network, and no installed fonts, so it functions with no
internet access.

Telemetry is pushed to connected clients over a WebSocket at the acquisition rate. Loss of
the client connection does not affect acquisition, logging, or interlock evaluation, all of
which run in the service independent of any observer.

## 8.5 State machine

```
  IDLE ──arm──▶ ARMED ──enable──▶ ENABLED ──stop──▶ STOPPED ──reset──▶ IDLE
                                                                          ▲
   any state ──e-stop or interlock trip──▶ FAULT ──reset───────────────────┘
```

| State | DAC0 | Meaning |
|---|---|---|
| IDLE | 0 V | No run in progress |
| ARMED | 0 V | Operator has confirmed intent. Gate still down |
| ENABLED | 5 V | Gate asserted. A `run_id` is allocated and logging begins |
| STOPPED | 0 V | Normal termination |
| FAULT | 0 V | Latched. Requires explicit operator reset |

Enable is a separate step from Arm so that the SSR closes into a de-energised circuit. The
transition is refused if measured current exceeds 0.10 A, enforcing the requirement that
the relay never makes a live load.

## 8.6 Acquisition and timing

| Channel group | Rate | Mechanism |
|---|---|---|
| Current, voltage, temperature, flow, interlock readback | 20 Hz | Single batched LJM call per cycle |
| Optical power | 12 Hz | Independent thread, cached, consumed by the main loop |

All T7 channels are read in one batched call so they share a single scan and therefore a
single timestamp. Timestamps derive from a monotonic clock anchored once to wall time at
service start, so they are immune to wall-clock adjustment mid-run.

### 8.6.1 Single clock domain

Because the Ophir is read by the same process that reads the T7, **optical and electrical
samples are timestamped by the same clock.** No inter-machine clock synchronisation,
offset estimation, or timestamp reconciliation is performed or required.

The residual timing error between an electrical event and its optical measurement is
therefore the physical response of the thermopile plus the USB round trip, and is a
property of the instrument rather than of the data system. It remains subject to
measurement by cross-correlation against a shared ramp event, per Objective 7.

## 8.7 Data recording

Every sample is written to InfluxDB tagged with stand identifier, mode, state, and
`run_id`. A `run_id` is allocated on each Enable transition, making runs individually
retrievable and comparable.

Operator events (arm, enable, stop, fault, marker) are written to a separate measurement
and surface in Grafana as annotations across all panels. Markers placed at the start and
end of each irradiance ramp are the mechanism by which ramp events are located in the data.

Raw sensor voltages are recorded alongside the scaled engineering values, so any run can be
recomputed after the fact if a calibration constant is subsequently corrected.

Writes are batched and buffered. A transient database outage does not interrupt acquisition
or interlock evaluation.

## 8.8 Network configuration

| Mode | `wlan0` | Pi address | Use |
|---|---|---|---|
| Bench | client, joins site WiFi | DHCP | Development, image caching, time sync |
| **Field** | **access point, SSID `leolaser`, WPA2** | **10.42.0.1** | Testing |

`eth0` is unused. The access point profile is configured not to start automatically, so the
bench path to the Pi cannot be lost by a reconfiguration error.

The Pi serves time to clients via chrony. Absolute time is maintained across power cycles by
a hardware real-time clock. Without it, timestamps after a field reboot are absolute-time
incorrect, which does not corrupt intra-run timing but does prevent time-range queries from
locating the data.

## 8.9 Verification tools

Standalone diagnostics, independent of the control service. The service must be stopped
before use, as only one process may hold each instrument.

| Tool | Verifies |
|---|---|
| `check_labjack.py` | Identity, firmware, ADC noise floor, every analog and digital channel, thermistor conversion, pulse counter, DAC loopback, scan latency against the 20 Hz budget |
| `check_ophir.py` | USB enumeration, device identification, sensor channel discovery, live power streaming |
| `check_network.py` | Reachability, service ports, health endpoints, acquisition counters |

`check_labjack.py` asserts DAC0 only under an explicit flag and a typed confirmation, and
returns both DACs to 0 V on every exit path including abnormal termination.

## 8.10 Failure behaviour

| Condition | Behaviour |
|---|---|
| Instrument read failure while energised | Software interlock trip. Gate voltage removed, FAULT latched, cause recorded |
| Control service restart | Gate driven to 0 V before any other device access |
| T7 power cycle with no service running | Gate remains at 0 V |
| Ophir disconnected | Optical channel ages out and is flagged stale. Electrical acquisition unaffected |
| Database unreachable | Writes buffered. Acquisition and interlocks unaffected |
| Operator client disconnected | Acquisition, logging, and interlocks unaffected |
| Loss of network entirely | Acquisition, logging, and interlocks unaffected. Operator visibility lost |

No software function is credited as protection for the laser diode. The acquisition
interval is 50 ms against a failure mode that develops in microseconds. Software provides
orderly shutdown, annunciation, and an attributable record; transient protection is
hardware, per §7.3.
