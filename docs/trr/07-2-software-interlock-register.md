# TRR §7.2 — Software Interlocks

## 7.2.1 Scope and limitation

The interlocks in this section are implemented in the acquisition service
(`app/main.py`, function `check_limits`) and evaluated once per acquisition cycle at
`SAMPLE_HZ` = 20 Hz.

**These interlocks are not credited as protection for the laser diode.** Catastrophic
optical damage develops on a microsecond timescale. The nominal detection latency of this
layer is one sample interval, 50 ms, and the worst case is unbounded under loop overrun.
The gap is three to four orders of magnitude.

Their credited functions are: orderly shutdown, annunciation, and creation of an
attributable fault record. Protection against overcurrent transients is provided solely by
the hardware analog comparator of DD-03, in §7.3.

## 7.2.2 Common trip action

Every interlock in Table 1 invokes the same action, `trip()`:

1. `DAC0` driven to 0.0 V, de-energising the interlock chain and the SSR.
2. State machine latched to `FAULT`.
3. Fault reason recorded to the event log and written to InfluxDB.
4. Reason broadcast to all connected clients.

`FAULT` is latching. Recovery requires an explicit operator `/reset`, which is rejected from
any state other than `STOPPED` or `FAULT`.

## Table 1 — Implemented software interlocks

| ID | Interlock type | Function and trip condition | Channel | Threshold | Configuration key |
|---|---|---|---|---|---|
| SW-1 | **Comparator latch relay** | Trips if the hardware comparator of DD-03 has latched. Software mirrors the hardware trip so the cause is recorded; it does not effect the trip | FIO3 | logic low | `COMPARATOR_WIRED` |
| SW-2 | **Current clamp** | Trips if HASS-derived forward current exceeds the operating red line | AIN0 | > 11.0 A | `CURRENT_REDLINE_A` |
| SW-3 | **Overtemperature clamp** | Trips if housing temperature exceeds the datasheet maximum | AIN3, AIN-EF 50 | > 30.0 °C | `TEMP_LIMIT_C` |
| SW-4 | **Coolant flow clamp** | Trips if measured coolant flow falls below minimum. Rate derived over a 2 s rolling window | FIO0, DIO-EF counter | < 2.0 LPM | `FLOW_MIN_LPM` |
| SW-5 | **Interlock chain monitor** | Trips if node X readback is low after the post-enable settling window has elapsed. Detects both a switch opening mid-run and a chain that never closed on enable | FIO1 | logic low, sustained | `INTERLOCK_CONFIRM_S` = 0.6 s |
| SW-6 | **Acquisition integrity** | Trips on any exception raised by the acquisition source while energised. Prevents operation on stale data | all | any read failure | — |

Evaluation is short-circuiting and in the order listed, so the recorded reason is the first
condition satisfied.

SW-5 requires a settling window because FIO1 reads node X, which is `DAC0` *through* the
switch chain. With `DAC0` at 0 V the chain is unpowered and FIO1 must read low irrespective
of switch state. The chain is therefore only observable after enable, and the window
accommodates SSR and contactor pull-in.

## Table 2 — Pre-enable permissives

Evaluated on the `/enable` transition. Failure returns HTTP 409 and no state change occurs.

| ID | Permissive | Condition | Rationale |
|---|---|---|---|
| PE-1 | State gate | Current state must be `ARMED` | Enforces the two-step arm-then-enable sequence |
| PE-2 | **Zero-current gate** | Measured current magnitude ≤ 0.10 A | The SSR must never make a live load. Enforces DD-11 at the software boundary |

## Table 3 — Failsafe defaults

| ID | Condition | Behaviour |
|---|---|---|
| FS-1 | Device handle opened | `DAC0` written to 0.0 V before any other register access |
| FS-2 | Service start | Source constructed with enable de-asserted |
| FS-3 | Service shutdown, including exception paths | `DAC0` driven to 0.0 V, then the handle is closed |
| FS-4 | T7 power cycle with no service running | `DAC0` remains at 0 V. Verified in bring-up |
| FS-5 | Any switch in the hardwired chain opens | SSR control pulled to 0 V by the 30 kΩ FIO1 divider to ground, independent of software |

## Table 4 — Specified but NOT yet implemented

| ID | Interlock type | Specified in | Status |
|---|---|---|---|
| SW-7 | **Voltage clamp, over** | — | **Not implemented.** Trip on `V > 42.0 V` while energised. An open-circuit or disconnected load allows the array to drive toward Voc = 80.6 V |
| SW-8 | **Voltage clamp, under** | — | **Not implemented.** Trip on `V < 36.0 V` with `I > 2.0 A`. Indicates a partial short or a degraded junction |
| SW-9 | **Optical deficit** | Addendum R-2 | **Not implemented.** Trip on `Δ_opt > 0.15` at steady state. This is the only available indicator of facet damage |
| SW-10 | **Optical staleness** | Addendum R-6 | **Not implemented.** `optical_age_s` is computed and published but not evaluated as a trip |
| SW-11 | **Ramp rate clamp** | Stage 2 Yellow | **Not implemented.** Annunciate on any inter-sample current step exceeding 0.5 A |
| SW-12 | **Loop overrun clamp** | — | **Not implemented.** `loop_overruns` is counted but not evaluated. A sustained overrun invalidates the latency assumption of this entire layer |

Absent SW-7 and SW-8 there is no software supervision of the voltage channel at all. The
absence is material: an open-circuit load is the fault condition under which the array
attains its maximum voltage, and it is currently undetected.
