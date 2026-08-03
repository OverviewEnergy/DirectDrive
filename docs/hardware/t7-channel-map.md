# T7 Channel Map

Definitive allocation. Supersedes §1 of `PINOUT.md`; the per-sensor electrical detail in
§§2–7 of that document still stands. If code and this table disagree, fix the code.

Connection: **ETHERNET**, static 192.168.2.2/24. `LABJACK_CONN=ETHERNET`, `LABJACK_ID=<ip>`.

---

## 1. Wired now

| Terminal | Sensor / signal | Direction | Scaling | Read as |
|---|---|---|---|---|
| **AIN0** | LEM HASS 50-S `Uout` | in, single-ended, ±10 V | `I = (V − V_zero) / (0.0125 × N)` | `current_a` |
| **AIN1** | 10 kΩ NTC on the laser housing | in, AIN-EF 50 | Steinhart-Hart, 4-term, in firmware | `temp_c` |
| **AIN2** | LJTick-Divider-25 ch A | in, 0–3.5 V | `V = 25 × V_ain` | `voltage_v` |
| **AIN3** | — | none | — | physically covered by the LJTick module |
| **FIO0** | Koolance INS-FM17N reed | in, DIO-EF counter, 3.3k/6.8k divider from VS | `LPM = 0.307 × Hz` (10 mm nozzle) | `flow_lpm` |
| **FIO1** | Node X interlock readback | in, digital | 10k/20k divider, 5 V → 3.33 V | `interlock_closed` |
| **DAC0** | SSR enable, via the interlock chain | out, 0–5 V | 5.0 = enabled, 0.0 = safe | `enable` |
| **200UA** | AIN1 excitation | out, fixed | bridged to AIN1, two wires in one terminal | — |
| **VS** | 5 V rail | out | HASS supply, FIO0 pull-up | — |
| **GND** | Common return, single-point tie to node N | — | — | — |

**Analog inputs available on screw terminals: zero.** AIN0–AIN3 are the only analog
terminals on the T7; AIN4–AIN13 exist only on the DB37 connector. AIN3 is not recoverable
while the LJTick-Divider is fitted.

**Free on screw terminals: DAC1, FIO2, FIO3.** Everything past that needs a CB37 breakout.

---

## 1a. FIO0 reed divider sizing

Do not use the T7's internal pull-up. It is ~100 kΩ, which gives 33 µA of closed-contact
current. A mechanical contact needs milliamps to break through its own oxide film, so a
weak pull-up produces intermittently missed closures that read as low, stable, plausible
flow. It also leaves the line at 100 kΩ next to a switched 10 A conductor.

```
  VS ──[ 3.3 kΩ ]──┬──▶ FIO0
                   │
                [ 6.8 kΩ ]
                   │
                  GND ──── reed wire B
```

| | 10k/20k | 3.3k/6.8k |
|---|---|---|
| Closed-contact current | 0.5 mA | **1.5 mA** |
| High level | 3.33 V | 3.37 V |
| Thevenin impedance | 10 kΩ | **2.2 kΩ** |
| Margin to Koolance's 10 mA max | 20× | 6.7× |

The divider exists to cap the high level below the 3.3 V logic maximum. A single pull-up to
VS puts 5 V on the pin and relies on the internal clamp as a regulator. If the unit exposes
a 3.3 V terminal, use one 2.2 kΩ from it instead and skip the divider.

No capacitor on this line: the DIO-EF debounce handles bounce in firmware and a cap only
slows the edge.

---

## 2. Planned additions and where they land

| Terminal | Signal | Requirement | Rationale |
|---|---|---|---|
| **FIO2** | 1-Wire bus, 4× DS18B20 | DD-RQ-030, and coolant logging | One pin and a 4.7 kΩ pull-up to VS covers four sensors. See §3 |
| **FIO3** | Comparator trip latch readback | DD-RQ-004 | Digital in. Without it, a comparator trip is indistinguishable from a switch opening and the fault record is useless |
| **DAC1** | unused, reserved | — | Consumed by the LJTick-OutBuff block if the contactor needs buffering |
| — | DC contactor coil | DD-RQ-026 | Wired from **node X**, in hardware, alongside the SSR control. Not a LabJack channel. See §5 for the current budget |
| — | Analog comparator | DD-RQ-004 | Taps HASS `Uout` in parallel with AIN0, opens the interlock chain directly. Not a LabJack channel |

After this the screw terminals are full and the next addition forces a CB37.

---

## 3. FIO2 — the 1-Wire temperature bus

Four temperature channels are now required and there is exactly one analog input with an
excitation source, already taken. Adding analog thermistors does not fit and would need a
CB37 plus an external excitation network per channel. Use a digital bus instead.

| Sensor | Location | Purpose |
|---|---|---|
| `t_module` | rear of one PV module, foil-taped | DD-RQ-030. Sets the compliance edge |
| `t_coolant_in` | supply line, waterproof probe | run card 1.3.6, 3.4.3 |
| `t_coolant_out` | return line, waterproof probe | coolant dT, closes the thermal balance |
| `t_ambient` | shaded, in free air | dewpoint reference for DD-RQ-023 |

```
  VS ──[ 4.7 kΩ ]──┬──▶ FIO2
                   │
                   ├── DS18B20 DQ  (×4, parasitic power off, VDD to VS)
                   │
                  GND ── DS18B20 GND, common
```

Why 1-Wire over analog thermistors or I2C:

- One pin for all four, versus four analog inputs plus four excitation networks.
- Designed for multi-metre runs. The module sensor is 1 to 2 m from the board and I2C at
  that distance outdoors is fragile.
- Outputs °C directly. No Steinhart-Hart, no calibration, no compliance limit, no
  four-term coefficient trap.
- Waterproof stainless probes are a commodity part, which is what the coolant lines want.
- ±0.5 °C, which is far better than needed for a compliance-edge lookup or a dewpoint margin.

**Keep AIN1 analog.** The laser housing thermistor stays on AIN1 as an analog AIN-EF
channel. It is the one temperature that is safety-relevant, the T7 computes it in firmware
with no bus transaction, and it reads at full loop rate.

### Read cadence

A DS18B20 12-bit conversion takes up to 750 ms, and the T7 addresses one ROM per
transaction. Four sensors cannot be read inside a 20 Hz loop.

Read the bus on a **separate 0.5 Hz task** and cache the values. The main loop consumes the
cache. All four are slow thermal signals; none of them changes meaningfully inside 2 s.
Publish a staleness field per channel so a dead sensor reads as stale rather than as a
frozen plausible number.

---

## 4. Fault discrimination, and what is deliberately not instrumented

FIO1 reads node X, which is the **aggregate** of key switch, lid switch, and flow switch in
series. It cannot tell you which one opened.

Individual readbacks would need three more digital inputs and therefore a CB37. Not worth
it, because:

- Flow is already measured independently on FIO0, so a flow trip is visible in the data.
- The key switch and lid switch are physical and in front of the operator.
- The run card verifies all three independently before every run.

What *does* need its own line is the comparator, on FIO3, because a fast trip is invisible
in every other channel and is the one fault whose cause you cannot reconstruct after the
fact.

---

## 5. Current budgets

### DAC0, ~15 mA hard limit

| Load | Draw |
|---|---|
| SSR control input at 5 V | **UNVERIFIED**, must be < 15 mA |
| FIO1 readback divider, 30 kΩ | 167 µA |
| DC contactor coil | 50–500 mA typical, **does not fit** |

The contactor forces a buffer. Either an **LJTick-OutBuff** on the DAC block, which drives
200 mA and consumes DAC0+DAC1, or an interposing relay driven from node X. Measure the SSR
control current before deciding, since it may already be most of the budget.

### VS

| Load | Draw |
|---|---|
| HASS 50-S | 19 mA typ, 25 mA max |
| FIO0 pull-up, 10 kΩ, contact closed | 0.5 mA |
| FIO2 1-Wire pull-up, 4.7 kΩ | ~1 mA |
| DS18B20 × 4, converting | ~6 mA |
| FIO1 divider | 0.17 mA |
| **Total** | **~33 mA** |

Comfortable on an externally powered T7. Confirm the actual VS budget for your supply
arrangement, and keep the HASS on a clean regulated rail per `PINOUT.md` §2, since
single-ended wiring passes supply drift straight into the zero.

---

## 6. Derived channels, computed in software

Not terminals. Listed so the data model is complete.

| Field | From | Notes |
|---|---|---|
| `power_w` | AIN0 × AIN2 | electrical input |
| `resistance_ohm` | AIN2 / AIN0 | guard against divide-by-zero at low current |
| `coolant_dt_c` | `t_coolant_out − t_coolant_in` | |
| `heat_removed_w` | flow × dT × ρ × cp | cross-check against `power_w` minus optical |
| `dewpoint_c` | `t_ambient` + humidity | needs a humidity source, currently manual |
| `droop_pct` | AIN0 vs Isc at `t_module` | DD-RQ-031 compliance margin |
| `optical_w` | Ophir, over HTTP | separate clock domain, carries its own timestamp |
| `loop_dt_s` | monotonic clock | loop health |

---

## 7. Verification items

Carried from `PINOUT.md` §8, plus the new ones.

| # | Item |
|---|---|
| 1 | `DIO_EF_COUNTER_INDEX`, currently a placeholder of 9 |
| 2 | Steinhart-Hart coefficients on AIN1, currently placeholders, four-term not three |
| 3 | Laser V− actually at LabJack ground, else use dual-ended sense on `VINB` |
| 4 | SSR DC rating, and control current against the DAC0 budget |
| 5 | Thermistor minimum temperature against the 200 µA compliance limit, ~15 kΩ, ~10 °C |
| 6 | Maintained-contact flow switch sourced, separate from the FM17N |
| 7 | **T7 1-Wire register set and function support for the installed firmware** |
| 8 | **DS18B20 ROM addresses enumerated and pinned to roles in config**, so a swapped probe cannot silently relabel a channel |
| 9 | **Contactor coil current, and whether an OutBuff or interposing relay is needed** |
