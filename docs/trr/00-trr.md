# Test Readiness Review — PV Direct-Drive Laser Demonstration

| | |
|---|---|
| Revision | B, 5 August 2026 |
| TRR date | Wednesday 5 August |
| Gates | Load testing (resistive) and Direct Drive (diode) |

---

## 1. Goals and Purpose

An nLight n24i laser diode is normally driven by a laser diode driver (LDD), which regulates
current, provides soft start and soft stop, and clamps faults. This demonstration removes
the driver and drives the diode directly from a photovoltaic array, using the intersection
of the panel IV curve and the diode IV curve to set the operating point.

A PV panel below its Vmp behaves as a current source with high output impedance, which is
what a laser diode wants. It is dangerous because that intersection is a nominal point with
no active clamp: anything that lifts the source curve lifts the current, and catastrophic
optical damage (COD) happens in microseconds. No software in this system protects against
that.

**Primary purpose:** determine whether a PV array can drive a high-power laser diode safely
and repeatably without a driver, and quantify the operating point, the turn-on and turn-off
transients, and optical output versus irradiance.

**Secondary purpose:** establish the irradiance-ramp method that makes the transition to and
from the operating point survivable, and produce the LDD-versus-direct-drive comparison
requested by the SME.

---

## 2. Objectives

1. Operate the diode from the PV array at its operating point and hold it there for a
   continuous run, logging current, voltage, housing temperature, coolant flow, and optical
   output.
2. Keep diode current inside the absolute maximum at all times, by procedure and by the
   hardware trip.
3. Capture the turn-on and turn-off transients and show peak current stays inside the
   absolute maximum.
4. Show no irreversible degradation: optical output at a fixed current repeatable run to
   run within measurement uncertainty.
5. Determine which uncovering method gives the smoothest current ramp on this panel's
   three-substring geometry.

---

## 3. Roles and Responsibilities

| Role | Responsibility | Owner |
|---|---|---|
| Test Director | Overall authority, go/no-go, criteria sign-off | Taiki Yamauchi |
| Test Conductor | Runs the procedure, commands state transitions, keeps the logbook | Taiki Yamauchi |
| Laser Safety Officer | Beam containment, eyewear specification, controlled-area boundary, sign-off on protection layers | Jordan Leidner |
| Safety Checkout | Safe-operating-mode shakeout / safety walkthrough. Enclosure, signage, leak detection | Paul Jaffe, Michael Liang, Ted Proctor |
| Software + DAQ | Service modules, GUI | Taiki Yamauchi |
| Thermal / Fluids | Chiller, radiator, coolant loop | Robert Johnson |
| Electrical | Interlock wiring, grounding/ESD | Robert Johnson, Samuel Herman |

---

## 4. Device Under Test

| Item | Detail |
|---|---|
| Laser diode | nLight n24i, fiber-coupled pigtail |
| Rated optical | 230 W CW |
| Threshold / slope | 1.4 A, 21.5 W/A |
| Operating current | 12.1 to 14 A |
| Operating voltage | 38.5 to 39.5 V |
| Housing temperature | 0 to 30 °C |
| Source | 2× Renogy RNG-320D in **series**. Voc 80.6 V, Vmp 66.0 V, Isc 10.23 A, Imp 9.70 A (label values) |
| Irradiance control | Opaque cover, progressively peeled back |
| Current sensor | LEM HASS 50-S, 12.5 mV/A, <4 µs, 240 kHz |
| Voltage sensor | LJTick-Divider-25 on a LabJack T7 |
| Optical | Ophir Juno + FL400A-BB-50, 400 W continuous |
| Controller | Raspberry Pi 5, FastAPI service, InfluxDB, Grafana |
| Location | Outdoors, alongside the array |

### Predicted operating point

Series string at 38 to 39.5 V sits at 58 to 60% of Vmp, deep in the current-source region.
Current varies by 0.0007 A across that whole band, so it is Isc to within 0.02%.

| Quantity | At STC | At 60 °C module, 1000 W/m² |
|---|---|---|
| Current | 10.23 A | 10.34 A |
| Voltage | 38.5 to 39.5 V | same, set by the diode |
| Electrical in | 399 W | 403 W |
| Optical out | ~190 W | ~192 W |
| Waste heat | ~209 W | ~211 W |

---

## 5. Requirements

| ID | Requirement | Basis |
|---|---|---|
| DD-01 | Array in **series**, not parallel | 39 V is 0.58 × Vmp in series, in the flat region. Parallel puts 39 V past Vmp on the steep, temperature-sensitive part of the curve |
| DD-02 | Diode current never exceeds **______ A** *(set at TRR)* | Absolute max 12.1 A. See §6 for the irradiance that reaches it |
| DD-03 | Hardware fast trip: analog comparator on HASS `Uout`, latching, opens the interlock chain directly | COD is microseconds. Software polls at 20 Hz. Software cannot close that gap. **In or out — TRR decision** |
| DD-04 | Reverse-parallel clamp diode across the laser | Laser diode reverse breakdown is a few volts. Loop ringing after any interruption can reverse-bias it. Separate from the TVS decision |
| DD-05 | No TVS fitted | Accepted. Operating current is well below absolute maximum and the procedure shades to zero before any switching, so there is no current for loop inductance to work against. Residual exposure is unplanned interruption only |
| DD-06 | No capacitance across the diode | Q = C·V dumps into the facet on any switching event, and a capacitor looks like a short to a fast transient, destroying the current-source protection |
| DD-07 | Housing temperature ≤ 30 °C, target 25 °C | Datasheet range 0 to 30 °C. COD threshold falls as junction temperature rises |
| DD-08 | Coolant flow before power, always. Maintained-contact flow switch in the hardwired chain | 211 W of waste heat with no flow |
| DD-09 | Chiller setpoint ≥ dewpoint + 3 °C, and ≤ 28 °C | Condensation on the diode package is a failure. A Virginia August dewpoint of 22 to 24 °C leaves a narrow window against the 30 °C limit |
| DD-10 | Every interlock switch de-energizes the SSR in hardware, verified one switch at a time | The entire safety argument rests on this property |
| DD-11 | Turn-off order: cover to zero current, confirm zero on two instruments, then open the SSR | Interrupting current through loop inductance produces a voltage kick. With DD-05 accepted, procedure is the mitigation |
| DD-12 | ≥ 2 independent protection layers between laser light and any person at all times | LSO |
| DD-13 | Beam fully contained. Fiber inside conduit, constrained every 10 cm, terminating inside a closed enclosure | Outdoors there is no room boundary to serve as a layer. Fiber failure at 190 W whips |
| DD-14 | Fiber end face inspected under a scope before every energized run. Never energize an open connector | Contamination at 190 W destroys the face in one shot. The most common way fiber-coupled diodes die |
| DD-15 | Beam termination standoff set so the spot is 30 to 40 mm at the absorber, inside the 50 mm aperture. Absorber tilted 5 to 10° off normal | At a bare fiber tip 190 W is hundreds of kW/cm². Standoff is what makes the FL400A survive. Tilt prevents retro-reflection into the emitter |
| DD-16 | Enclosure light-tight at the sensor aperture | A thermopile cannot distinguish laser light from sunlight. 1000 W/m² across the aperture is ~2 W of offset, and it varies with irradiance, which is the independent variable |
| DD-17 | Eyewear OD **______** at **______** nm, staged at the boundary, worn by all present | Wavelength unresolved. **TRR decision** |
| DD-18 | Back-of-module temperature logged | The current-source compliance edge falls from 57.9 V at a 25 °C cell to 44.2 V at 65 °C. Without it, a droop measurement cannot be interpreted |
| DD-19 | DAC0 at 0 V on power-up, after restart, and after comms loss | Verified in bring-up |

---

## 6. Test Stages

| Stage | Config | Entrance | Success | Red |
|---|---|---|---|---|
| **1. Load test** Mon/Tue | 1 panel, 5 Ω on cold plate, 5 W to 276 W | Bring-up passed, HASS verified, interlock chain verified switch by switch | Current and voltage within 1% of DMM at three power levels; every fault de-energizes the load; 276 W soak 10 min with stable temperatures | Any fault fails to de-energize, or DAQ error > 2% |
| **2. Direct drive** Thu | Diode, 2 panels series | Stage 1 signed, TRR signed, §9 checklist complete | Diode reaches steady state from the array; current inside DD-02; optical within 15% of the value predicted from threshold and slope; clean ramp in and out | Current over absolute max; optical more than 15% below prediction, which indicates facet damage |

### Irradiance and current, panel fully uncovered

Module at 60 °C, which is what 92 °F ambient in full sun gives. Isc coefficient +0.03%/°C.

| Irradiance | Current | Note |
|---|---|---|
| 800 W/m² | 8.27 A | |
| 900 | 9.30 A | |
| 1000 | 10.34 A | typical clear-sky peak here in August |
| 1100 | 11.37 A | |
| **~1170** | **12.1 A** | **absolute maximum reached** |
| 1300 | 13.44 A | cloud-edge enhancement |

Full uncover is inside the diode's absolute maximum on a stable clear sky. The margin is
consumed by cloud-edge enhancement, which can briefly exceed 1200 W/m².

**Operating rule: no diode run under broken cloud.** Thursday is forecast 25% rain, so
sky condition is a go/no-go item on the run card, not a note.

---

## 7. Safety

### 7.1 Hazards

| Hazard | Magnitude |
|---|---|
| Optical, Class 4 NIR, invisible | ~190 W CW, plus diffuse reflections |
| Electrical shock | 80.6 V DC open circuit, live whenever the panels see light |
| No off switch | Covering the panel is the only way to de-energize the source |
| Thermal, coolant loss | 211 W into the diode with no flow |
| Fiber failure | Whip, and cladding-light burn-through on over-bend |
| Arc flash on DC interruption | An AC-rated breaker cannot interrupt DC arc |

### 7.2 Protection layers

| Layer | Implementation |
|---|---|
| 1 | Fiber jacket |
| 2 | Metal conduit over the full fiber run, plus the closed enclosure containing the FL400A. Seams and viewports taped |
| 3 | Fenced controlled-area boundary, signage with wavelength and point of contact, eyewear staged at the boundary |

### 7.3 Interlock chain

```
DAC0 ─▶ key switch ─▶ lid switch ─▶ maintained flow switch ─▶ node X ─▶ SSR control (+)
                                                                │
                                                       10k/20k ─▶ FIO1 readback
                                             SSR control (−) ─▶ GND
```

Independent of software state. The 30 kΩ to ground doubles as the pull-down giving the SSR
a defined 0 V the instant any switch opens.

Software interlocks — flow rate, housing temperature, optical sanity, loop timing — run at
20 Hz. They exist to shut down in an orderly way and to record why. **None of them is fast
enough to protect the diode and none is credited as protection.**

### 7.4 Emergency

- Emergency card posted at the stand. Pre-test briefing before every run.
- **On any anomaly: cover the panel first.** Opening the SSR under load is itself a hazard.
- E-stop drops DAC0 and latches FAULT. It may break a live load. That risk is to the diode,
  not to you. **If a person is at risk, hit E-stop.**
- Coolant leak: cover the panel, cut power, stop the chiller, contain.
- Eyewear worn by everyone present from the moment the cover comes off.

---

## 8. Risks

| Risk | Consequence | Mitigation |
|---|---|---|
| Cloud-edge irradiance spike | Diode over absolute maximum | No runs under broken cloud. Comparator trip if fitted. Sky condition is a go/no-go |
| COD from a turn-on transient | Diode destroyed | Uncover slowly rather than switching electrically. No capacitance across the diode |
| SSR opened under load | L·di/dt kick, reverse bias | Turn-off order DD-11, written as a hard gate in the run card |
| **SSR fails shorted** | No switch, no E-stop, no software action removes current. Only the breaker and the cover remain | Series DC contactor. **Not fitted. Open item** |
| Fiber end-face contamination | Diode destroyed on the next shot | Scope inspection before every run, connector capped when unmated |
| Wrong standoff at the absorber | FL400A destroyed | DD-15, standoff measured and mechanically fixed before first light |
| Coolant loss during a run | Diode overheat | Maintained flow switch in the hardwired chain |
| Wrong part number, wrong current limit | Every current limit provisional | nLight datasheet requested. **Open item** |
| Condensation on the package | Diode failure | DD-09, dewpoint measured every run |
| Slow degradation missed | Campaign conclusions invalid | Optical output at fixed current compared run to run, every run |

---

## 9. Readiness Checklist

| Item | ☐ |
|---|---|
| Objectives and success criteria agreed | ☐ |
| HASS rework complete, 2.5 V reference confirmed, 12.0 A ±1% at 10 turns | ☐ |
| Interlock chain verified, each switch independently, load disconnected | ☐ |
| Maintained-contact flow switch fitted, not a substitute | ☐ |
| DAC0 confirmed 0 V on power-up, after restart, after comms loss | ☐ |
| Comparator fitted and trip-tested, **or** explicitly risk-accepted at the TRR | ☐ |
| Reverse-parallel clamp diode fitted | ☐ |
| Coolant loop leak-checked, flow ≥ 4 LPM, dewpoint measured, setpoint above it | ☐ |
| Fiber in conduit, constrained every 10 cm, end face scope-inspected | ☐ |
| Beam termination standoff measured and mechanically fixed | ☐ |
| Enclosure light-tight, verified with the array uncovered and the diode off | ☐ |
| Protection layers 1 to 3 in place, audited by the LSO | ☐ |
| Eyewear OD documented and staged | ☐ |
| Controlled area fenced, signage posted | ☐ |
| Stage 1 load test complete and signed | ☐ |
| Data logging verified, run records retrievable | ☐ |
| Emergency card posted, extinguisher located, briefing held | ☐ |
| Open items closed or explicitly risk-accepted | ☐ |

---

## 10. Open Items to Close at the TRR

| # | Item | Decision needed |
|---|---|---|
| 1 | Operating current limit, DD-02 | Set the number. Absolute max is 12.1 A on the e24i datasheet; the n24i datasheet is outstanding |
| 2 | Comparator, DD-03 | Fit it, or risk-accept in writing. It is the only protection against COD |
| 3 | Beam termination standoff, DD-15 | Needs fiber core diameter and NA to compute |
| 4 | Eyewear OD and wavelength, DD-17 | Blocked on the wavelength question below |
| 5 | Wavelength | Stated ~960 nm; the e24i datasheet says 878.6 nm. Unexplained |
| 6 | Series DC contactor | A shorted SSR is currently uncovered by every switch and by the E-stop |
| 7 | Maintained flow switch | The pulsing FM17N cannot sit in the hardwired chain |
| 8 | Parasitics ops guide vs Thursday firing | Both due Thursday. Decide when the guide gets written |

---

## 11. Approvals

| Role | Name | Signature | Date |
|---|---|---|---|
| Test Director | Taiki Yamauchi | | |
| Laser Safety Officer | Jordan Leidner | | |
| Safety Checkout | | | |
| Thermal / Fluids | Robert Johnson | | |
| Electrical | | | |
