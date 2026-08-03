# TRR Addendum — Abort Criteria and Irradiance Measurement

For insertion into `TRR_REV_B.md`. §A replaces the informal Red column of the Stage 2
test matrix. §B is a new requirement and method.

---

# §A. Abort Criteria

## A.1 Definitions

| Symbol | Quantity | Value | Source |
|---|---|---|---|
| `I_max` | Absolute maximum forward current | 12.1 A | e24i datasheet. **Provisional pending n24i data** |
| `I_rl` | Operating red line | ______ A | Set at TRR per DD-02 |
| `I_th` | Threshold current | 1.4 A | Datasheet |
| `η` | Slope efficiency | 21.5 W/A | Derived, 230 W / (12.1 − 1.4) A |
| `P_pred` | Predicted optical output | `η · (I − I_th)` | Computed per sample |
| `P_opt` | Measured optical output | — | Ophir FL400A-BB-50 |
| `Δ_opt` | Optical deficit | `(P_pred − P_opt) / P_pred` | Computed per sample |

## A.2 Condition classification

| Class | Definition | Required action |
|---|---|---|
| **Green** | All monitored parameters within nominal bounds | Continue |
| **Yellow** | Any parameter outside nominal but within abort limits | Arrest the irradiance ramp. Re-shade to reduce current. Hold and reassess. Test Conductor may resume at Test Director's discretion |
| **Red** | Any condition in A.3 satisfied | Execute emergency shutdown per §7.4. Stage recorded FAILED. No resumption without Test Director authorisation |

## A.3 Red conditions, Stage 2

### R-1 · Overcurrent

Measured forward current exceeds `I_max` at any instant.

**Detection:** analog comparator latch, read at FIO3, is the primary means. The DAQ current
channel at AIN0, sampled at 20 Hz, is a secondary and non-credited means.

**Basis:** `I_max` is a manufacturer absolute maximum rating. Exceedance permits damage
irrespective of duration, and the device is to be treated as suspect thereafter regardless
of subsequent apparent function.

**Note on detection adequacy.** Catastrophic optical damage develops on a microsecond
timescale. The 20 Hz DAQ channel has a 50 ms sampling interval and cannot detect a
transient excursion. R-1 is credited only where the comparator of DD-03 is fitted and
trip-tested. Absent the comparator, R-1 detection is limited to sustained excursions and
this limitation shall be recorded as an accepted risk.

### R-2 · Optical output deficit

`Δ_opt > 0.15` at any steady-state operating point, evaluated with forward current within
±2% of its 10 s mean.

**Detection:** DAQ, computed per sample from AIN0 and the Ophir channel.

**Basis.** Optical output at known forward current is the only available indicator of facet
condition. A deficit against prediction indicates that injected current is no longer
producing the expected photon flux, which is the observable signature of catastrophic
optical damage to the emitting facet.

**Threshold derivation.** Combined 1σ measurement uncertainty, root-sum-square:

| Contribution | 1σ |
|---|---|
| Ophir thermopile calibration | 3.0% |
| HASS current channel | 1.0% |
| Slope efficiency, datasheet tolerance | 5.0% |
| Thermal drift over a run | 2.0% |
| **Combined** | **6.2%** |

The 15% threshold is 2.4σ, placing it above the noise floor while remaining below the
smallest damage magnitude of consequence.

### R-3 · Loss of coolant flow

Measured flow below 2.0 LPM, or hardwired flow switch open.

### R-4 · Housing overtemperature

Measured housing temperature exceeds 30 °C.

### R-5 · Interlock chain open

Node X readback low, persisting beyond the 0.6 s post-enable settling window.

### R-6 · Loss of instrumentation

Acquisition read failure, or optical sample age exceeding 2.0 s, while the diode is
energised.

## A.4 Yellow conditions, Stage 2

| ID | Condition | Rationale |
|---|---|---|
| Y-1 | `I_rl < I` ≤ `I_max` | Operating red line exceeded, absolute maximum not yet reached |
| Y-2 | `0.08 < Δ_opt ≤ 0.15` | Above 2.1σ. Indicative but not conclusive |
| Y-3 | Run-to-run optical output at matched current differs by more than 8% | Run-to-run comparison cancels the slope-efficiency systematic, giving a 3.7% combined 1σ. 8% is 2.1σ |
| Y-4 | Flow between 2.0 and 4.0 LPM | Above interlock trip, below nominal |
| Y-5 | Housing temperature between 28 and 30 °C | Approaching datasheet limit |
| Y-6 | Sky condition transitions to broken cloud | Cloud-edge enhancement can exceed 1200 W/m² |

## A.5 Post-run evaluation

Following every energised run, the Test Conductor shall record `Δ_opt` at the steady-state
operating point and compare against all previous runs at matched forward current.

Evaluation is **mandatory per run and not deferrable to end of campaign.** A monotonic
degradation of 5% per run is undetectable by inspection but destroys the diode over six
runs, and once the trend is evident by eye the attribution to a specific run is no longer
recoverable.

---

# §B. Irradiance Measurement

## B.1 Requirement

**DD-33.** Plane-of-array irradiance shall be measured and recorded at each of: pre-test,
every steady-state operating point, at any Yellow or Red event, and post-test.

**Basis.** Forward current is a function of irradiance and cell temperature alone; the diode
voltage is invariant over the operating band. Irradiance is therefore the sole independent
variable of the experiment. Absent its measurement, no operating point is reproducible, the
IV model cannot be validated against measurement, and a current excursion cannot be
attributed to its cause.

## B.2 Method 1 — Array short-circuit current (primary, available immediately)

Short-circuit current is linear in irradiance. The array is therefore its own pyranometer,
and a superior one: it responds in the panel's own spectral band, at the panel's own tilt
and azimuth, which is precisely the quantity of interest.

```
                    I_sc,meas
   G  =  1000  ·  ─────────────  ·  ────────────────────────
                    I_sc,STC          1 + α·(T_cell − 25)
```

| Parameter | Value |
|---|---|
| `I_sc,STC` | 10.23 A, label value |
| `α` | +0.0003 /°C |
| `T_cell` | Back-of-module temperature per DD-30 |

**Procedure.** Array uncovered, load side shorted through the HASS window with a shorting
link, SSR closed. Record current. Restore configuration.

**Temperature correction is not optional.** At a 60 °C module the uncorrected reading is
1.05% high, which propagates directly into the derived irradiance.

**Limitation.** Requires the load to be disconnected, and is therefore a discrete
measurement taken before and after a run, not a continuous channel. Not usable with the
diode in circuit.

## B.3 Method 2 — Dedicated reference cell on AIN1 (recommended)

Relocating the thermistor to AIN3 has freed AIN1, which is the only remaining analog input
and is well suited to this purpose.

A silicon pyranometer with millivolt output, cosine-corrected, wired directly to AIN1
configured on the ±1 V range. Representative part: Apogee SP-110, 0 to 350 mV over 0 to
1750 W/m², approximately $200.

| Property | Value |
|---|---|
| Channel | AIN1, ±1 V range, resolution index 8 |
| Scaling | `G = V_ain / sensitivity`, sensitivity per calibration certificate |
| Cadence | Continuous, at full loop rate |

This provides a continuous logged irradiance channel concurrent with the diode run, which
Method 1 cannot. It is the configuration required for Objective 5, determination of the
ramp method, since that objective requires irradiance and current to be correlated in time.

## B.4 Method 3 — Modelled irradiance (reference only)

Clear-sky and satellite-derived irradiance for the site may be obtained from the NREL
National Solar Radiation Database or equivalent, and recorded as a plausibility reference.

**Not credited as measurement.** Modelled data is hourly, horizontal-plane, and derived from
satellite retrieval. It cannot resolve the plane-of-array value, cannot resolve cloud-edge
enhancement, and cannot resolve the ramp.

## B.5 Cross-check using the FL400A

The FL400A-BB-50 is a broadband thermopile of 50 mm aperture, 19.6 cm². At 1000 W/m² normal
incidence it would register approximately 2.0 W, within its 300 mW to 400 W range.

Admissible as a one-time sanity cross-check against Method 1. **Not admissible as
measurement:** the sensor is calibrated at laser wavelengths, has no cosine diffuser, and
requires manual normal-incidence alignment. Solar spectral content outside the calibrated
band introduces uncharacterised error.

## B.6 Recording

The following shall be entered on the run card at each measurement point.

| Field | Units |
|---|---|
| Irradiance, plane of array | W/m² |
| Method used | 1 / 2 / 3 |
| Back-of-module temperature | °C |
| Sky condition | clear / hazy / scattered / broken |
| Derived predicted current at this irradiance | A |
| Measured current | A |
| Deviation from prediction | % |

The final two rows constitute a continuous validation of the IV model against measurement
and are the primary quantitative product of Stage 1.
