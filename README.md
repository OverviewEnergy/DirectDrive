# PV Direct-Drive Laser Test Stand

Driving an nLight n24i laser diode directly from a photovoltaic array, with no laser diode
driver in the circuit.

A laser diode is normally fed by a driver that regulates current, ramps softly, and clamps
faults. This stand removes it. The operating point is set by the intersection of the panel's
IV curve and the diode's IV curve, and irradiance is the only control input.

It works because a PV panel operated well below its maximum power point behaves as a stiff
current source, which is what a laser diode wants. It is dangerous because that intersection
has no active clamp, and catastrophic optical damage develops in microseconds.

---

## Predicted operating point

Two Renogy RNG-320D in series, label values Voc 80.6 V, Vmp 66.0 V, Isc 10.23 A, Imp 9.70 A.

| | Value |
|---|---|
| Diode voltage | 38.5 to 39.5 V, set by the diode |
| Array current | **10.23 A**, essentially Isc |
| Electrical in | 399 W |
| Optical out | ~190 W |
| Array MPP, for comparison | 642 W at 67.4 V |

At 39 V the string sits at 58% of Vmp, deep in the current-source region: current varies by
0.0007 A across the whole 38.0 to 39.5 V band. The diode pins the voltage, the panel sets
the current, and neither can push the other around.

The 243 W difference between the operating point and MPP is not recoverable. Maximum power
transfer occurs precisely where the small-signal resistance equals the static resistance,
which is the point at which the panel stops behaving as a current source. Stiffness and
power are mutually exclusive demands on the same quantity.

---

## Architecture

```
   LabJack T7 ──────USB──────▶┐
                              │   Raspberry Pi 5
   Ophir Juno ──────USB──────▶┤     leolaser-api   :8000   control + acquisition + GUI
   + FL400A-BB-50             │     influxdb       :8086   time-series storage
                              │     grafana        :3000   dashboards
                              └────────────┬───────────────
                                           │  WiFi, Pi in access point mode
                                           ▼
                                  Operator laptop, browser only
```

Both instruments are on USB to the Pi, so optical and electrical samples share one clock.
No inter-machine time synchronisation is performed or needed. No external network is
required: the Pi hosts its own access point and DHCP.

---

## Quick start

```bash
cp .env.example .env          # then edit, see below
./install/setup_pi.sh         # venv, deps, LJM check, systemd unit
docker compose pull           # cache images while you still have internet
docker compose up -d          # influxdb + grafana
sudo systemctl start leolaser-api
curl -s localhost:8000/health # influx_reachable must be true
```

Control panel at `http://<pi>:8000/`, Grafana at `http://<pi>:3000/`.

`SOURCE=sim` in `.env` runs the entire stack with no hardware attached, on the real operating
point. Use it to exercise the GUI, the dashboards, and every fault path before touching the
array.

Full walkthrough from fully unplugged: **[docs/cold-start.md](docs/cold-start.md)**

---

## Configuration values that will lie to you

These do not error. They produce plausible, wrong numbers.

| Key | Fix with |
|---|---|
| `HASS_ZERO_V` | `bench_checks/check_labjack.py`. Do not assume 2.5 |
| `SH_A` … `SH_D` | `tools/calibrate_thermistor.py`. Four-term, not three |
| `DIO_EF_COUNTER_INDEX` | T7 DIO-EF docs for the installed firmware |
| `FLOW_LPM_PER_HZ` | 0.307 for the 10 mm nozzle, 0.28 for the 6 mm |

A wrong `DIO_EF_COUNTER_INDEX` gives a counter that never increments, faithfully reported as
a clean and stable 0.00 LPM.

---

## Repository map

| Path | Contents |
|---|---|
| `app/` | Control service. Runs natively on the Pi so it can reach USB without passthrough |
| `bench_checks/` | Standalone hardware diagnostics. No dependency on the service |
| `tools/` | Bring-up utilities. Run on the Pi host with the service stopped |
| `bridge/` | Legacy Windows-side Ophir sender. Superseded by direct USB, kept as a fallback |
| `grafana/` | Provisioned datasource and dashboard |
| `install/` | systemd unit, udev rule, host setup script |
| `docs/` | Cold start, field config, TRR, procedures. See [docs/README.md](docs/README.md) |

Only one process may hold each instrument. Stop the service before running anything in
`tools/` or `bench_checks/`.

---

## Safety

**No software in this system protects the laser diode.** The acquisition loop runs at 20 Hz,
a 50 ms interval, against a failure mode that develops in microseconds. The software
interlocks exist to shut down in an orderly way, to annunciate, and to produce an
attributable fault record. Transient overcurrent protection is a hardware analog comparator
on the current-sensor output, and nothing else.

The hardwired interlock chain is the safety argument:

```
DAC0 ─▶ E-stop ─▶ rotary key ─▶ lid switch ─▶ coolant switch ─▶ node X ─▶ SSR gate
```

Any element opening removes the SSR gate voltage in hardware, independent of software state.
This property is verified one switch at a time before every test session. It is either
tested or it is assumed.

Shutdown order is mandatory: **cover the array, confirm zero current on two instruments,
then open the SSR.** The relay must never break a live load. Covering the array is also the
only way to de-energise the source, since a solar panel has no off switch.

See [docs/trr/00-trr.md](docs/trr/00-trr.md).

---

## Status

**Complete:** software stack, GUI, dashboards, interlock chain, bring-up tooling, direct USB
Ophir driver, TRR through §8.

**Open, blocking diode operation:**

| Item | Why it blocks |
|---|---|
| Analog comparator on the current sensor | The only protection against catastrophic optical damage |
| Reverse-parallel clamp diode | Laser diode reverse breakdown is a few volts |
| Real n24i datasheet | Every current limit is provisional. Stated 960 nm conflicts with the e24i datasheet's 878.6 nm |
| Series DC contactor | A shorted SSR is uncovered by every switch and by the E-stop |
| Maintained-contact flow switch | The pulsing flow meter cannot sit in the hardwired chain |
| Beam termination standoff | Requires fiber core diameter and NA to compute |
| Eyewear OD | Blocked on the wavelength question |

**Known errors in earlier project state, corrected here:** the two-panel series current at
the operating point was recorded as 6.13 A, which is the one-panel figure; the correct value
is 10.23 A. A series ballast resistor was listed as an overcurrent mitigation; against a
source in its current-source region it changes the voltage division and not the current.
