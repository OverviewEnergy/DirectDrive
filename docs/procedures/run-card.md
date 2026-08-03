# Test Procedure, PV Direct-Drive Laser Stand

Print one per run. Every block gets a completion timestamp. Do not skip forward.

| Field | Entry |
|---|---|
| Date | |
| Test Conductor | |
| Test Director | |
| LSO present (Stages 3 to 5 only) | |
| Second person present | |

## Test information

| # | Field | Options | Entry |
|---|---|---|---|
| 0.1 | Test title | | |
| 0.2 | Test purpose | | |
| 0.3 | Desired outcome | | |
| 0.4 | Stage | ☐ 0 bring-up ☐ 1 resistive ☐ 2 source char ☐ 3 LDD baseline ☐ 4 direct drive ☐ 5 characterization | |
| 0.5 | Operation type | ☐ Functional check ☐ Power check ☐ Characterization run ☐ Endurance run | |
| 0.6 | Load under test | ☐ 5 Ω ☐ 2 Ω ☐ 4 Ω ☐ Laser diode | |
| 0.7 | Array configuration | ☐ Disconnected ☐ 1 panel ☐ 2 panels series | |
| 0.8 | Scrim fitted | ☐ Yes, ______ % transmission ☐ No, load cannot be overdriven | |
| 0.9 | Current source | ☐ PV array ☐ Laser diode driver | |
| 0.10 | MODE tag | ☐ ldd ☐ direct_drive | |
| 0.11 | Predicted current at operating point | ______ A | |
| 0.12 | Red-line current for this run | ______ A | |

---

# 1. Setup

## 1.1 Confirm test configuration

| # | Item | Check / entry |
|---|---|---|
| 1.1.1 | Breaker OPEN, SSR de-energized, array covered | ☐ |
| 1.1.2 | Load resistance measured cold, or diode part verified | ______ Ω / ______ |
| 1.1.3 | Load mounted to cold plate with paste, full contact | ☐ |
| 1.1.4 | Wiring matches the connection table, checked point to point | ☐ |
| 1.1.5 | No capacitance across the load | ☐ |
| 1.1.6 | Clamp diode and TVS fitted (Stages 3 to 5) | ☐ N/A ☐ |
| 1.1.7 | Comparator installed, trip verified at ______ A (Stages 3 to 5) | ☐ N/A ☐ |
| 1.1.8 | Oscilloscope on HASS Uout, triggered, armed | ☐ |
| 1.1.8a | Fiber end face inspected under a scope, clean (Stages 3 to 5) | ☐ N/A ☐ |
| 1.1.8b | Fiber constrained every 10 cm, inside conduit, off the ground, no bend below minimum radius | ☐ N/A ☐ |
| 1.1.8c | Fiber tip standoff to absorber measured, spot 30 to 40 mm inside the 50 mm aperture | ______ mm |
| 1.1.8d | Absorber tilted 5 to 10° off normal, no flat normal-incidence surface in the path | ☐ N/A ☐ |
| 1.1.8e | Enclosure internal temperature at the sensor | ______ °C, ≤ 25 |
| 1.1.9 | Node N to LabJack GND measured | ______ V, must be ≈ 0 |
| 1.1.10 | Single-point ground confirmed, no second path | ☐ |
| **Completed** | YYYY-MM-DD hh:mm:ss EDT | |

**1.1.9 decides whether every voltage number in this run is real.** Two ground ties produce
a plausible-looking wrong answer.

## 1.2 Pre-test safety verification

| # | Safety check | Done |
|---|---|---|
| 1.2.1 | Pre-test briefing held, beam path and boundary covered, stop authority named | ☐ |
| 1.2.2 | Emergency card posted, extinguisher located | ☐ |
| 1.2.3 | Enclosure closed, beam path fully contained including the termination | ☐ N/A ☐ |
| 1.2.4 | Viewports and seams taped, no light leak path | ☐ N/A ☐ by LSO |
| 1.2.5 | Controlled-area boundary set, signage posted with wavelength and PoC | ☐ N/A ☐ by LSO |
| 1.2.6 | Eyewear worn by everyone present, OD ______ at ______ nm | ☐ N/A ☐ by LSO |
| 1.2.7 | Second person present and briefed | ☐ N/A ☐ |
| 1.2.8 | E-stop verified: press, confirm DAC0 drops and state latches FAULT, reset | ☐ |
| 1.2.8a | Contactor audibly drops on E-stop, and load-side continuity is broken | ☐ |
| 1.2.8b | **Shorted-SSR test.** Load disconnected, SSR control jumpered ON, then open each interlock switch. Contactor must drop every time | ☐ |
| 1.2.9 | Lid interlock verified: open the lid, confirm node X to 0 V | ☐ |
| 1.2.10 | Key switch verified: turn off, confirm node X to 0 V | ☐ |
| 1.2.11 | Flow switch verified: interrupt flow, confirm node X to 0 V | ☐ |
| 1.2.12 | Setup photos taken and uploaded, at least one | ☐ |
| 1.2.13 | Nothing combustible within 1 m of the load | ☐ |
| **Completed** | YYYY-MM-DD hh:mm:ss EDT | |

1.2.9 through 1.2.11 are **three separate tests**, one switch at a time, others closed. The
whole safety argument is that each switch breaks the loop independently. That is either
tested every run or it is assumed.

## 1.3 Enable coolant

| # | Item | Check / entry |
|---|---|---|
| 1.3.1 | Chiller AC connected | ☐ |
| 1.3.2 | Chiller on | ☐ |
| 1.3.3 | **Dewpoint measured** | ______ °C |
| 1.3.3a | Setpoint captured, must be ≥ dewpoint + 3 °C and ≤ 28 °C | ______ °C |
| 1.3.3b | No condensation visible on the cold plate, diode package, or lines | ☐ |
| 1.3.4 | Flow confirmed at the load, visually and on the flow meter | ______ LPM, ≥ 4 |
| 1.3.5 | No leaks anywhere in the loop, inspected | ☐ |
| 1.3.6 | Coolant supply and return temperatures noted | ______ / ______ °C |
| **Completed** | YYYY-MM-DD hh:mm:ss EDT | |

**Flow before power, always. No exceptions, including for short functional checks.** This
is exactly what the flow interlock exists for. Do not defeat it.

## 1.4 Configure array and shade

Skip for Stage 0 and Stage 3.

| # | Item | Check / entry |
|---|---|---|
| 1.4.1 | Panels wired in the intended configuration | ☐ |
| 1.4.2 | Array covered, DMM across the array output | ______ V, must be < 5 V |
| 1.4.3 | Uncover briefly, measure Voc, then re-cover | ______ V |
| 1.4.4 | Voc matches the configuration: ~40.3 V for one panel, ~80.6 V for two in series | ☐ |
| 1.4.4a | Panel serial numbers recorded, pairing unchanged from the last Isc measurement | ☐ |
| 1.4.5 | Scrim fitted and secured, cannot be displaced by wind. Transmission ≤ 80% | ☐ N/A ☐ |
| 1.4.6 | Shade method staged and reachable from the operating position | ☐ |
| 1.4.7 | Sky condition recorded | ☐ clear ☐ hazy ☐ scattered ☐ **broken** |
| 1.4.8 | Irradiance estimate or reference cell reading | ______ W/m² |
| 1.4.8a | **Back-of-module temperature** | ______ °C |
| 1.4.8b | 1% compliance edge at that temperature, from the TRR table | ______ V |
| 1.4.8c | Predicted operating voltage is below the edge | ☐ |
| 1.4.9 | **Dark-light check:** array fully uncovered, diode off, optical channel reads near zero | ______ W, must be < 1 |
| **Completed** | YYYY-MM-DD hh:mm:ss EDT | |

**1.4.4 catches a series-versus-parallel miswire before any current flows.** If two panels
read 40 V, they are in parallel and the diode would sit past Vmp.

**1.4.7: broken cloud is a no-go for Stages 4 and 5.** Cloud-edge irradiance can reach
1300 W/m², and the only thing standing between that and the diode is the scrim.

## 1.5 Close hardware interlock

| # | Item | Check / entry |
|---|---|---|
| 1.5.1 | E-stop pulled out | ☐ |
| 1.5.2 | Key switch on | ☐ |
| 1.5.3 | Lid closed and latched | ☐ |
| 1.5.4 | FIO1 readback HIGH, loop closed | ☐ |
| 1.5.5 | Breaker closed | ☐ |
| **Completed** | YYYY-MM-DD hh:mm:ss EDT | |

## 1.6 Transition to ARMED

| # | Item | Check / entry |
|---|---|---|
| 1.6.1 | Service healthy: `/health` shows influx_reachable true, points_written climbing | ☐ |
| 1.6.2 | Reset to IDLE if in STOPPED or FAULT | ☐ |
| 1.6.3 | HASS zero in use matches the measured value | ______ V |
| 1.6.4 | Press Arm, state = ARMED | ☐ |
| **Completed** | YYYY-MM-DD hh:mm:ss EDT | |

---

# 2. Startup

## 2.1 Verify interlock readback

| # | Item | Check / entry |
|---|---|---|
| 2.1.1 | Software interlock reads closed | ☐ |
| 2.1.2 | Grafana live: current, voltage, temperature, flow all updating | ☐ |
| 2.1.3 | `loop_dt_s` stable near 1/SAMPLE_HZ | ______ s |
| **Completed** | YYYY-MM-DD hh:mm:ss EDT | |

## 2.2 Verify zero state

| # | Item | Check / entry |
|---|---|---|
| 2.2.1 | Current reads 0.00 A with the array covered | ______ A |
| 2.2.2 | Voltage reads 0.0 V | ______ V |
| 2.2.3 | Load temperature at ambient | ______ °C |
| 2.2.4 | Optical channel reads near zero and stable, beam blocked (Stages 3 to 5) | ______ W |
| 2.2.5 | No faults or errors annunciated | ☐ |
| **Completed** | YYYY-MM-DD hh:mm:ss EDT | |

## 2.3 Transition to ENABLED

| # | Item | Check / entry |
|---|---|---|
| 2.3.1 | Confirm array still covered and current is zero before enabling | ☐ |
| 2.3.2 | Press Enable, state = ENABLED, new run_id minted | run_id ______ |
| 2.3.3 | Current still 0.00 A with the SSR now closed | ______ A |
| **Completed** | YYYY-MM-DD hh:mm:ss EDT | |

**2.3.1 and 2.3.3 together are the whole point of the two-step enable.** The SSR closes
into a dark array at zero current, so it never makes a live load and never generates a
switching transient.

---

# 3. Operation

## 3.1 Irradiance ramp up

| # | Item | Check / entry |
|---|---|---|
| 3.1.1 | Scope armed, sweep set to capture the ramp | ☐ |
| 3.1.2 | Press Mark: shade | ☐ |
| 3.1.3 | Uncover progressively over the planned interval | target ______ s |
| 3.1.4 | Ramp method used | ☐ scrim ☐ hard shade, ☐ long axis ☐ short axis |
| 3.1.5 | Watch current continuously during the ramp. Stop uncovering at the first sign of a step | ☐ |
| 3.1.6 | Largest observed current step | ______ A, red-line 0.5 A |
| 3.1.7 | Current at the point uncovering stopped | ______ A |
| **Completed** | YYYY-MM-DD hh:mm:ss EDT | |

**Abort criteria during the ramp.** Yellow: current within 1.1 A of the red line, or any
step above 0.5 A. Re-shade to reduce current, hold, reassess. Red: current above the
red line from 0.12, or optical output falls while current rises. **Re-shade immediately.
Do not reach for the SSR or the breaker.** Shade is the fast, safe control. The SSR under
load is a hazard of its own.

## 3.2 Verify operating point

| # | Item | Check / entry |
|---|---|---|
| 3.2.1 | Current, LabJack | ______ A |
| 3.2.2 | Current, DMM in series | ______ A, within 1% |
| 3.2.3 | Voltage, LabJack | ______ V |
| 3.2.4 | Voltage, DMM across the load | ______ V, within 1% |
| 3.2.5 | Sign positive | ☐ |
| 3.2.6 | Electrical power | ______ W |
| 3.2.7 | Against prediction from 0.11 | ☐ within 10% ☐ investigate |
| 3.2.8 | Back-of-module temperature at the operating point | ______ °C |
| 3.2.9 | Droop below Isc, and headroom to the 1% compliance edge | ______ % / ______ V |
| **Completed** | YYYY-MM-DD hh:mm:ss EDT | |

Negative current means the HASS conductor runs the wrong way through the window. Fix the
conductor, not the software.

## 3.3 Settle

| # | Item | Check / entry |
|---|---|---|
| 3.3.1 | Hold 120 s. No action. Watch temperature and current | ☐ |
| 3.3.2 | Current drift over the hold | ______ A |
| 3.3.3 | Load temperature trend | ☐ plateauing ☐ still rising ☐ **runaway, shut down** |
| **Completed** | YYYY-MM-DD hh:mm:ss EDT | |

## 3.4 Capture thermal

| # | Item | Check / entry |
|---|---|---|
| 3.4.1 | Load or laser housing temperature | ______ °C |
| 3.4.2 | Against limit: 30 °C for the diode, resistor rating for a resistor | ☐ pass ☐ yellow ☐ red |
| 3.4.3 | Coolant supply / return | ______ / ______ °C |
| 3.4.4 | Coolant dT against prediction | ______ °C |
| 3.4.5 | Flow under thermal load | ______ LPM |
| **Completed** | YYYY-MM-DD hh:mm:ss EDT | |

## 3.5 Capture optical

Stages 3 to 5 only.

| # | Item | Check / entry |
|---|---|---|
| 3.5.1 | Optical power, Ophir | ______ W |
| 3.5.2 | Predicted from the Stage 3 slope at this current | ______ W |
| 3.5.3 | Deviation | ______ %, red-line 15% low |
| 3.5.4 | Sensor fan running, airflow confirmed, exhaust not recirculating | ☐ |
| 3.5.4a | Enclosure internal temperature at the sensor, under load | ______ °C, ≤ 25 |
| 3.5.4b | Elapsed time on the absorber this run | ______ min, ≤ 10 without a separate dump |
| 3.5.5 | `optical_age_s` reasonable, `rejected_out_of_order` at 0 | ☐ |
| 3.5.6 | Sync offset stable, uncertainty well under 50 ms | ______ ms |
| **Completed** | YYYY-MM-DD hh:mm:ss EDT | |

**3.5.3 is the degradation check and it is the reason this run card exists.** Optical
output below prediction at a known current means the facet has already been damaged. Compare
against the Stage 3 baseline after every single run, not at the end of the campaign.

## 3.6 Capture transient records

| # | Item | Check / entry |
|---|---|---|
| 3.6.1 | Scope trace of the turn-on ramp saved | filename ______ |
| 3.6.2 | Peak current excursion above steady state | ______ A |
| 3.6.3 | Resistance measured hot, resistive stages | ______ Ω |
| 3.6.4 | Sky condition and irradiance at steady state | ______ |
| **Completed** | YYYY-MM-DD hh:mm:ss EDT | |

---

# 4. Shutdown

**Order is mandatory. Shade, confirm zero, then switch. Never the reverse.**

## 4.1 De-ramp irradiance

| # | Item | Check / entry |
|---|---|---|
| 4.1.1 | Press Mark: shade | ☐ |
| 4.1.2 | Re-cover progressively, mirroring the ramp-up interval | ☐ |
| 4.1.3 | Current confirmed at 0.00 A on the LabJack **and** the DMM | ______ / ______ A |
| 4.1.4 | Optical confirmed at zero | ______ W |
| **Completed** | YYYY-MM-DD hh:mm:ss EDT | |

**Do not proceed past 4.1.3 until current is actually zero on both instruments.** Everything
below this line breaks a circuit, and breaking a live circuit is what produces the L·di/dt
kick that this whole procedure exists to avoid.

## 4.2 Stop

| # | Item | Check / entry |
|---|---|---|
| 4.2.1 | Press Stop, state = STOPPED | ☐ |
| 4.2.2 | DAC0 at 0 V, FIO1 readback low | ☐ |
| 4.2.3 | SSR open, load-side continuity broken | ☐ |
| 4.2.4 | Current still 0.00 A, no transient recorded on the scope | ☐ |
| **Completed** | YYYY-MM-DD hh:mm:ss EDT | |

## 4.3 Isolate

| # | Item | Check / entry |
|---|---|---|
| 4.3.1 | Breaker open. Positive pole, or both poles. The node N tie is never switched | ☐ |
| 4.3.2 | Key switch off | ☐ |
| 4.3.3 | Array voltage at the load side | ______ V, must be 0 |
| **Completed** | YYYY-MM-DD hh:mm:ss EDT | |

Note that the array itself is still live at up to 80 V whenever it sees light. Shade is the
only off switch a solar panel has.

## 4.4 Coolant off

| # | Item | Check / entry |
|---|---|---|
| 4.4.1 | Load temperature below 40 °C before stopping flow | ______ °C |
| 4.4.2 | Chiller off | ☐ |
| 4.4.3 | Flow drops to zero, flow channel reads 0 | ☐ |
| **Completed** | YYYY-MM-DD hh:mm:ss EDT | |

Let the load cool with flow running. Stopping the chiller on a hot load soaks all the stored
heat back into the part.

## 4.5 Results

| # | Item | Check / entry |
|---|---|---|
| 4.5.1 | Test result | ☐ Success ☐ Partial ☐ Fail |
| 4.5.2 | Red-line exceeded at any point | ☐ No ☐ Yes, detail below |
| 4.5.3 | run_id recorded and data verified retrievable from InfluxDB | ☐ |
| 4.5.4 | Scope traces and photos filed | ☐ |
| 4.5.5 | Optical output versus Stage 3 baseline, degradation check | ______ % |
| 4.5.6 | Anomalies, in full | |
| 4.5.7 | Actions arising | |
| 4.5.8 | Debrief held, note taker assigned | ☐ |
| 4.5.9 | Non-present authorities notified of completion | ☐ |
| **Completed** | YYYY-MM-DD hh:mm:ss EDT | |

---

## Emergency shutdown

Any anomaly, any doubt:

1. **Shade the array.** This is the fastest safe action and it is always correct.
2. Confirm current at zero.
3. Press Stop, or E-stop if the situation is uncontrolled.
4. Open the breaker.
5. Leave coolant running until the load is below 40 °C.
6. Do not re-energize. Debrief first.

E-stop is available at any time and always correct if a person is at risk. It drops DAC0
and opens the SSR immediately, which may break a live load. **That risk is to the diode, not
to you. If a person is at risk, hit E-stop.**

---

## Final sign-off

| Role | Name | Signature | Date |
|---|---|---|---|
| Test Conductor | | | |
| Test Director | | | |
| LSO, Stages 3 to 5 | | | |
