# Rework Sheet

Three confirmed miswires. Do these in order, power off, before any further bring-up.

**Power down everything first.** Breaker open, T7 unpowered, 5 V rails off, load disconnected.

---

## Rework 1 — HASS 50-S, all four pins

Currently wired to the datasheet numbering read in the wrong direction. Identify pin 1 from
the **physical key on the Molex 5045-04 housing**, the moulded triangle or "1". Do not count
from an end.

| Pin | Signal | Remove from | Connect to |
|---|---|---|---|
| 1 | `Uref` | VS | **nothing. Leave floating** |
| 2 | `Output` | GND | **AIN0** |
| 3 | `0 V` | AIN0 | **GND** |
| 4 | `+5 V` | — | VS, or clean regulated 5 V. Already correct |

Passives, if not already fitted:

- 10 kΩ from `Output` to `0 V`. The datasheet specifies its accuracy into a 10 kΩ load.
- Optional 4.7 nF across the same two points for noise.

If pin 4 goes to an external supply rather than VS, its ground reaches LabJack GND through
pin 3 only. Confirm there is no second tie, or the single-point ground is broken.

☐ Rework 1 complete

---

## Rework 2 — thermistor from AIN3 to AIN1

AIN3 is physically covered by the LJTick-Divider module and is not wirable. Move it.

```
   thermistor leg 1  ─────┬───▶  200UA terminal
                          │
                          └───▶  AIN1        (two wires share the 200UA terminal)
   thermistor leg 2  ──────────▶  GND
```

Two-wire NTC, no polarity. Nothing goes through the LJTick.

☐ Old wire removed from the AIN3 position or `VINB`
☐ 200UA bridged to AIN1
☐ Rework 2 complete

---

## Rework 3 — SSR control return from DAC1 to GND

| Signal | Remove from | Connect to |
|---|---|---|
| `SSR control −` | DAC1 | **GND** |

DAC1 returns to unused. A T7 DAC is a voltage output and cannot be used as a return path.

☐ Rework 3 complete

---

## Rework 4 — verify the interlock chain is actually in the circuit

Not a rework if it is already correct, but it must be confirmed before anything else is
trusted.

```
  DAC0 ──▶ key switch ──▶ lid switch ──▶ maintained flow switch ──▶ node X
                                                                      │
                                        ┌─────────────────────────────┤
                                        ▼                             ▼
                                 SSR control (+)              10k/20k to FIO1
                                        │
                                 SSR control (−) ──▶ GND
```

**Test, load disconnected:**

| Step | Expected | ☐ |
|---|---|---|
| DAC0 = 5.0 V, all switches closed, DMM on `SSR control +` | ~5 V | ☐ |
| Open the key switch | **drops to 0 V** | ☐ |
| Close key, open the lid switch | **drops to 0 V** | ☐ |
| Close lid, open the flow switch | **drops to 0 V** | ☐ |
| FIO1 divider present, node X to FIO1 reads ~3.33 V when closed | ~3.33 V | ☐ |

If `SSR control +` holds 5 V with a switch open, DAC0 is wired directly to the SSR and the
hardwired chain is not in the circuit. Stop and rewire.

☐ Rework 4 complete

---

## Post-rework verification, in this order

Nothing here needs the panel. Do it all on the bench.

| # | Step | Pass criteria | ☐ |
|---|---|---|---|
| 1 | **Remove the LJTick-Divider module.** `bringup.py --selftest` needs the AIN3 screw terminal for the DAC0 loopback | module off | ☐ |
| 2 | `bringup.py --selftest` | AIN15 within ±2.000 mV **with variation**; DAC0→AIN3 loopback within 50 mV at every setpoint | ☐ |
| 3 | Confirm DAC1 still functions, since it may have been sinking current out of spec | responds to a commanded value | ☐ |
| 4 | Refit the LJTick-Divider module | | ☐ |
| 5 | Power the HASS, load disconnected, nothing through the window. Read AIN0 | **~2.5 V, small variation** | ☐ |
| 6 | `bringup.py --zero-hass`, record the actual zero | V_zero = ______ V | ☐ |
| 7 | 10 turns through the window at 1.2 A | displays 12.0 A ±1% | ☐ |
| 8 | Reverse the conductor | sign flips | ☐ |
| 9 | Thermistor on AIN1 reads plausible ambient | within a few °C of a reference | ☐ |
| 10 | Substitute a precision 10 kΩ for the thermistor | reads near 25 °C | ☐ |
| 11 | `bringup.py --interlock-test`, load disconnected | each switch independently drops node X | ☐ |
| 12 | Power-cycle the T7 with no software running | DAC0 stays 0 V | ☐ |

### Step 5 is the one that tells you whether the HASS survived

| AIN0 reads | Verdict |
|---|---|
| ~2.5 V, small variation | wiring correct, reference buffer alive |
| near 5 V, static | `Uref` still on a rail, or the reference buffer is damaged |
| near 0 V | output still shorted, or no supply |
| drifting, noisy, floating | `0 V` pin still not on GND |
| ~2.5 V but **no response** at step 7 | reference alive, **Hall front end or output driver damaged.** Replace the sensor |

A static reading with no variation at all is a fail even if the number looks right. That is
the signature of a dead channel, not a quiet one.

---

## Notes
