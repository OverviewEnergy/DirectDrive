# Findings

Analysis and defects found while building this stand. Recorded because the conclusions are
not obvious from the code, and several of them corrected earlier work.

---

## 1. Errors found in prior analysis

### 1.1 Two-panel series current was recorded as 6.13 A

`PROJECT_STATE.json` listed 6.13 A at 38 V and 3.91 A at 39 V for the series configuration.
Those are the **one-panel** figures, copied into the two-panel table.

For the series string, `k = C2 · Voc = 4.932`, so at 38 V the exponential correction term
contributes 1.8×10⁻⁴ and the current is **10.228 A**, essentially Isc.

The tell was internal inconsistency: the same document estimated 185 W optical output, and
`(10.23 − 1.4) × 21.5 = 190 W`. At 6.13 A the same slope gives 102 W. Only one of those two
numbers could be right.

### 1.2 A series ballast resistor does not limit overcurrent

Listed as an overcurrent mitigation in three places. Against a source operating in its
current-source region a series resistor changes the voltage division, not the current.

To pull 13.3 A down to 12.1 A you would have to push the panel near its knee at roughly
78 V, requiring 3.25 Ω dissipating 470 W, and it would land the operating point on the
steep, badly conditioned part of the curve — the exact condition the series configuration
was chosen to avoid.

Replaced by a fixed neutral-density scrim, which is a passive and deterministic hardware
limit rather than one that only appears to exist.

### 1.3 Panel specifications were datasheet values, not label values

Label: Voc 40.3, Vmp 33.0, Isc 10.23, Imp 9.70. Datasheet copy in use: Voc 40.1, Vmp 33.7,
Isc 10.08, Imp 9.50. Both give 320 W, but the fill factor differs, 0.776 against 0.792.

Refitting the model moved four things:

| | Datasheet copy | Label |
|---|---|---|
| Operating current | 10.08 A | 10.23 A |
| Optical output | 187 W | 190 W |
| Required scrim transmission | 84% | **80%** |
| Irradiance at which the 11.0 A limit is breached | 1300 W/m² | **1100 W/m²** |

The last row is the consequential one. 1100 W/m² is a clear day with ground reflection, not
an exotic condition.

---

## 2. Why the array delivers short-circuit current

The most persistent confusion on this project, and worth stating plainly.

**Current is not a property of a device.** A device's IV curve is one equation in two
unknowns and has no solution. Connect two devices and Kirchhoff supplies two more
constraints — same current, same voltage — giving two equations in two unknowns and exactly
one solution. That intersection is where current comes from. It is a property of the pair.

The laser diode is roughly 20 forward-biased junctions in series. Junction current is
exponential in voltage, so voltage is logarithmic in current, so the diode holds ~39 V
almost regardless of current. It pins the voltage.

39 V is 58% of the string's 66 V Vmp. A cell's internal diode only begins stealing
photocurrent when the terminal voltage approaches Voc, which happens over roughly the last
15 V of the curve. At 39 V the correction term is 0.018%, so essentially all photocurrent
leaves through the terminals — the same as if the panel were shorted.

Hence Isc. Not because anything is shorted; 39 V and 399 W are flowing. The panel's output
has simply already saturated at that voltage.

**A higher-impedance load draws less current**, which is the opposite of the intuition that
usually gets applied here:

| Load | Static R | Operating point | Current |
|---|---|---|---|
| Dead short | 0 Ω | 0 V | 10.23 A |
| Laser diode | 3.81 Ω | 39 V | 10.23 A |
| 6.80 Ω | 6.80 Ω | 66 V (MPP) | 9.70 A |
| 10.8 Ω | 10.8 Ω | 75 V | 6.94 A |

---

## 3. Maximum power and current-source stiffness are mutually exclusive

Two different quantities get called resistance and conflating them is where the design
question lives.

- **Static:** `V / I`. Decides where on the curve you land.
- **Small-signal:** `dV / dI`. Decides how far the operating point moves when anything
  drifts.

Only the second predicts behaviour. For the laser diode they differ by 7×: 3.81 Ω static,
0.53 Ω small-signal.

Small-signal resistance also has a clean interpretation. A disturbance δV splits across
source and load impedances in series:

```
δI = δV / (r_source + r_load)
```

At 39 V the panel is 2219 Ω and the diode is 0.53 Ω, a ratio of **4200:1**. The diode's
forward voltage can drift 0.5 V over a run and the current moves 0.23 mA. Thermal runaway is
impossible because the source will not permit it.

### The theorem

Maximum power means `dP/dV = 0`. With `P = V·I`:

```
dP/dV = I + V·(dI/dV) = 0    ⟹    −dV/dI = V/I
```

**Maximum power transfer occurs exactly where the small-signal resistance equals the static
resistance.** Verified against the fitted model: the model's true MPP is 67.36 V, 9.532 A,
642.1 W, where static is 7.067 Ω and small-signal is 7.063 Ω.

Now the ratio of the two across the curve:

| V | dV/dI ÷ V/I | Power |
|---|---|---|
| 20 V | 53,471 | 205 W |
| **39 V** ← operating point | **582** | **399 W** |
| 60 V | 5.3 | 604 W |
| **67.4 V** ← MPP | **1.0** | **642 W** |
| 78 V | 0.04 | 327 W |

A stiff current source requires that ratio to be large. Maximum power requires it to be
exactly 1. Those are contradictory demands on one number, and not as an engineering
compromise: "maximum power point" is *defined* as where the ratio equals one.

So the 243 W gap between 399 W and 642 W is not recoverable and not a build defect. It is
what a bare panel is.

### What this means for the result

The array is oversized for one diode anyway. At absolute maximum the diode draws 12.1 A at
39 V, which is 472 W — less than the 642 W available. Even perfect MPP tracking would be
diode-limited.

| | Optical out |
|---|---|
| MPPT + LDD, diode-limited | 230 W |
| Direct drive | **190 W** |

**83% of rated optical output with zero active electronics in the path.** That is the
finding. "62% array utilisation" describes the same fact as a failure.

---

## 4. Compliance collapses roughly twice as fast as Voc

The voltage up to which the array still regulates current, tabulated by droop below Isc:

| Cell temp | 0.1% | 1% | 5% | Voc |
|---|---|---|---|---|
| 25 °C | 46.5 | 57.9 | 65.8 | 80.6 V |
| 45 °C | 38.9 | 51.0 | 59.5 | 75.3 V |
| 65 °C | 31.3 | 44.2 | 53.2 | 70.0 V |

Voc falls 13% from 25 °C to 65 °C. The 1% compliance edge falls **24%**. Two effects stack:
Voc drops at −0.33%/°C, and the knee simultaneously softens because `k` scales with thermal
voltage. Derating compliance by the Voc coefficient is wrong by a factor of two.

Consequence for the diode: headroom to the 1% edge is +18.9 V on a cool morning and **+4.9 V
at a 65 °C module.** Direct drive still works hot, but the comfortable-looking margin is a
cold-panel number.

This is why back-of-module temperature is a required measurement. Without it a droop
measurement cannot be interpreted and a thermal shift cannot be distinguished from a real
operating-point shift.

---

## 5. The 5 Ω resistor behaves completely differently on two panels

Same resistor, two configurations, because Rmpp doubles in series:

| Source | Rmpp | 5 Ω lands | V | I | P | I as % of Isc |
|---|---|---|---|---|---|---|
| One panel | 3.40 Ω | right of MPP, on the knee | 37.11 V | 7.42 A | 275 W | **72.6%** |
| Two in series | 6.80 Ω | left of MPP, current-source | 51.02 V | 10.20 A | **521 W** | 99.8% |

Two findings.

**One panel into 5 Ω does not test the current-source regime.** It sits on the knee at 73%
of Isc. Valid as instrument validation, but no conclusion about source behaviour follows
from it.

**Two panels into 5 Ω is 521 W**, 30% over a 400 W resistor, and at a 65 °C cell the
operating point falls 6 V *outside* the 1% compliance edge.

The right resistive proxy for the diode is its equivalent resistance, 39 / 10.23 = **3.81 Ω**:

| R | V | Error vs 39 V |
|---|---|---|
| 2 Ω | 20.46 V | −47.5% |
| 3.8 Ω | 38.87 V | **−0.3%** |
| 4 Ω | 40.91 V | +4.9% |
| 5 Ω | 51.02 V | +30.8% |

Also, in the current-source region resistor drift works against you: current is fixed at
Isc, so `P = Isc²R`, and a wirewound's positive tempco raises R, which raises dissipation,
which raises R. Bounded with a cold plate, but self-reinforcing. On the knee a rising R pulls
current down and partly cancels itself.

---

## 6. Software defects found

### 6.1 Flow rate was quantisation noise

At 5 LPM the reed runs at ~16 Hz against a 20 Hz acquisition loop. Differentiating the
counter per sample gives 0 or 1 pulses per tick, so flow quantised in ~1.25 LPM steps and
jumped between 0 and 6 LPM continuously.

Replaced with a rolling 2 s window: ±1 pulse in 32, about ±3%. Temperature and flow are slow
signals and do not need 20 Hz.

### 6.2 The interlock permissive could never pass

The `/enable` handler refused to proceed unless `interlock_closed` was already true. But FIO1
reads node X, which is DAC0 **through** the switch chain. With DAC0 at 0 V the chain is
unpowered and FIO1 reads low regardless of switch positions.

That check would have blocked enable permanently on real hardware, and it reviewed as
correct.

The chain is only observable *after* the gate is asserted. Replaced with a zero-current
permissive, which is checkable and enforces the requirement that the SSR never makes a live
load, plus a 0.6 s post-enable settling window after which an open chain trips. Strictly
better: it also detects a chain that fails to close, which the original could not.

### 6.3 A wrong DIO-EF counter index fails silently

It does not error. It produces a counter that never increments, faithfully reported as a
clean, stable, plausible 0.00 LPM. The index remains unverified against firmware and is
called out in `.env.example` and in the diagnostic output for that reason.

---

## 7. Measurement integrity

### 7.1 Using the power meter as the beam dump destroys the degradation measurement

The FL400A-BB-50 is rated 400 W continuously, so 190 W is within rating. But optical output
at known current is the **only** available indicator of facet condition. If the traceable
instrument is also absorbing 190 W for hours, a 5% drop is either facet damage or absorber
drift and the two cannot be separated.

Ophir specifies annual recalibration for a sensor not being used as a dump.

Acceptable for short first-light runs. Not acceptable for endurance, which needs a separate
dump plus a sampled tap.

### 7.2 Power density, not total power, is what destroys thermopiles

190 W at a bare 200 µm fiber tip is roughly 600 kW/cm². BB is Ophir's general-purpose
absorber, not the high-damage-threshold coating.

Standoff is the whole mitigation. At NA 0.22 the half-angle is 12.7°, so 70 to 90 mm from tip
to absorber gives a 32 to 40 mm spot inside the 50 mm aperture and 15 to 23 W/cm².

### 7.3 A thermopile cannot distinguish laser light from sunlight

1000 W/m² across the 50 mm aperture is about 2 W of offset on a 190 W reading. Only 1% — but
it varies **with irradiance**, which is the independent variable of the experiment.

An error correlated with the independent variable does not look like noise. It looks like
physics. Hence the requirement for a light-tight enclosure and a dark-light check with the
array uncovered and the diode off.

### 7.4 The array is a better pyranometer than a pyranometer

Isc is linear in irradiance, and the array responds in its own spectral band at its own tilt
and azimuth — precisely the quantity that sets the current. A commercial pyranometer measures
broadband horizontal irradiance and then needs spectral and geometric correction to get back
to what the panel sees.

```
G = 1000 · (Isc_meas / 10.23) / (1 + 0.0003·(T_cell − 25))
```

The temperature correction is not optional: at a 60 °C module the uncorrected value reads
1.05% high.

### 7.5 The optical deficit threshold, derived rather than chosen

Combined 1σ measurement uncertainty, root-sum-square:

| Contribution | 1σ |
|---|---|
| Ophir thermopile calibration | 3.0% |
| HASS current channel | 1.0% |
| Slope efficiency, datasheet tolerance | 5.0% |
| Thermal drift over a run | 2.0% |
| **Combined** | **6.2%** |

15% is 2.4σ. Run-to-run comparison cancels the slope-efficiency systematic, dropping the 1σ
to 3.7%, so the run-to-run threshold is 8% for the same 2.1σ. An earlier 5% run-to-run figure
was 1.3σ and would have tripped on noise.

---

## 8. Safety architecture gaps

### 8.1 A shorted SSR is uncovered by every interlock

A DC SSR is a MOSFET and its characteristic failure is drain-source short. The entire
interlock chain works by removing the SSR's control signal. With a shorted SSR, no switch, no
E-stop, no comparator, and no software action removes current. What remains is the manual
breaker and covering the array.

The fix is a **DC contactor in series**, driven from the same node, giving two dissimilar
break elements. The sequencing is free: both coils drop together, the SSR turns off in under
1 ms, a contactor armature parts in tens of ms, so current is already zero when the contacts
open. The semiconductor breaks the current, the contactor breaks the circuit, and no timers
or logic are interposed in the E-stop path.

There is also a software check that costs nothing: gate de-asserted and current flowing means
the relay has failed.

### 8.2 The E-stop belongs in the control circuit

Not the power path, for three reasons in increasing order of weight.

Pressing it in the power path would perform the one action the procedure forbids — breaking
a live load at 10.23 A — every single time.

IEC 60204-1 and ISO 13850 put the operator's contact in the control circuit and the switching
duty on a rated device.

And the contact would not survive. AC ratings do not transfer to DC, because a DC arc is
self-sustaining without a zero crossing. A block marked 240 VAC commonly has no DC rating
above 24 V. In the existing 5 V, sub-15 mA control circuit the rating question disappears
entirely.

### 8.3 Rate power-path devices off cold Voc, not STC Voc

Voc rises as the panel cools at −0.33%/°C:

| Cell temp | Series Voc |
|---|---|
| 25 °C | 80.6 V |
| −15 °C | **91.2 V** |

Rating off 80.6 V under-rates by 13%. Specify ≥ 100 VDC. Several parts sold as DC-rated are
15 A at 48 or 65 VDC.

### 8.4 Nothing electrical turns off a solar panel

An E-stop in the panel positive still leaves 90 V standing on the panel side of the open
contact. The E-stop's function here is to remove drive from the load. **Covering the array is
the only thing that de-energises the source**, which is why every shutdown sequence puts it
first.

---

## 9. Hardware defects found

### 9.1 Current sensor wired to a mirrored pin numbering

The connector drawing numbers pins **4 3 2 1** left to right. Counting left to right instead
produced: `Uref` on a 5 V rail, `Output` shorted to ground, and `0 V` on an analog input.

The consequence is worse than a wrong reading. With `0 V` not grounded, the die's ground
reference is established backwards through its own output stage, while that output stage is
shorted to ground, while the internal reference buffer fights a rail it cannot win against.
Three abuse conditions at once on the two components that determine whether the sensor
measures anything.

`Uref` on a rail is wrong under both numbering conventions, which makes it the invariant to
fix first.

### 9.2 Uref open and Uref grounded are not the same thing

`Uref` is an output by default: the sensor generates 2.5 V and presents it. Grounding it
forces the internal reference buffer to 0 V and it fights just as hard as the 5 V did. It
must be left floating.

### 9.3 The internal pull-up cannot drive a mechanical reed

The T7's internal pull-ups are ~100 kΩ, giving 33 µA of closed-contact current. A mechanical
contact needs milliamps to break through the oxide film on its faces. A weak pull-up produces
intermittently missed closures, which read as low, stable, plausible flow — the worst
available failure mode, because nothing looks broken.

3.3 kΩ / 6.8 kΩ from VS gives 1.5 mA of wetting current, a 3.37 V logic high below the pin's
3.3 V logic maximum, and a 2.2 kΩ Thevenin impedance instead of 100 kΩ next to a switched
10 A conductor.

### 9.4 The LJTick-Divider-25 is a two-channel module

Fitted to the AIN2/AIN3 block it drives **both** inputs, so AIN3 is not free. This was
unresolvable by discussion, so the analog channel assignment is parameterised in `.env`
instead of asserted in code.

---

## 10. Architectural simplification: the Ophir on Linux

The meter can be driven from Linux with pyusb and no vendor driver at all. Vendor 0x0BD3,
Juno 0x0778, ASCII commands wrapped `$<CMD>\r\n` over vendor-specific control transfers
(0x40/0x02 out, 0xC0/0x04 in), responses prefixed `*` or `?`.

| | Before | After |
|---|---|---|
| Machines in the data path | 2 | **1** |
| Vendor driver dependency | StarLab, Windows-only | **none** |
| Clock domains | 2, reconciled by an NTP-style exchange | **1** |
| Timing uncertainty | ~50 ms budget | same clock |

**The two-clock problem is eliminated, not reduced.** Optical and electrical samples are
timestamped by the same monotonic clock in the same process. The clock-sync exchange, offset
estimation, and the Windows bridge all become dead code.

What does not go away is the physical lag: a thermopile has a real thermal response time and
the USB round trip is nonzero. That remains worth measuring by cross-correlation, but it is
now an instrument property rather than a data-system problem.

---

## 11. Open items

Blocking diode operation:

| Item | Why |
|---|---|
| Analog comparator on the current sensor | The only protection against COD. Software polls at 20 Hz against a microsecond failure mode — a gap of three to four orders of magnitude that cannot be closed in software |
| Reverse-parallel clamp diode | Laser diode reverse breakdown is a few volts, and loop ringing after any interruption can reverse-bias it. Distinct from the TVS decision |
| Real n24i datasheet | Every current limit is provisional. Stated ~960 nm conflicts with the e24i datasheet's 878.6 nm, and eyewear OD cannot be specified until that is resolved |
| Series DC contactor | §8.1 |
| Maintained-contact flow switch | The pulsing flow meter would chop the gate line at the pulse rate |
| Beam termination standoff | Requires fiber core diameter and NA |

Not blocking, but unverified:

| Item | Risk if wrong |
|---|---|
| `DIO_EF_COUNTER_INDEX` | Silent zero flow |
| Steinhart-Hart coefficients | Confidently wrong temperature |
| `HASS_ZERO_V` | Offset error in every current reading |
| T7 1-Wire register set | 1-Wire subsystem disabled by default for this reason |
