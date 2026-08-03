# 7. Interlocks

## 7.1 Hardware Interlock

| Interlock Type | Function/Continuity conditions |
|---|---|
| Solid State Relay (SSR) | Disrupts main power line to laser |
| E-Stop | Continuous if Button is in the up state |
| Rotary Switch | Continuous if Rotary Key is turned to ON state |
| Coolant Switch | Continuous if coolant flow reaches above 2.0 LPM / 0.53 GPM |
| Lid Interlock Switch | Continuous if top enclosure lid is closed |

The SSR interrupts the main power line to the laser, and is normally open. The LabJack
provides a 5 V gate voltage that closes the relay, with an E-stop, Rotary Switch, Coolant
Switch, and Lid interlock in series with the gate voltage. Thus, any discontinuity within
these components disrupts the SSR gate voltage.

## 7.2 Software Interlock

| Interlock Type | Function/Continuity conditions |
|---|---|
| Current Clamp | Drops gate voltage if Hall-Effect sensor detects overcurrent conditions above 11.0 A |
| Voltage Clamp | Drops gate voltage if divider measures forward voltage outside the 36.0–42.0 V operating band |
| Temperature Clamp | Drops gate voltage if thermistor measures housing temperature above 30.0 °C |
| Coolant Flow Monitor | Drops gate voltage if flow rate falls below 2.0 LPM / 0.53 GPM |
| Interlock Readback | Drops gate voltage if node X readback indicates a hardware discontinuity |
| Data Integrity | Drops gate voltage if the DAQ fails to return a valid sample |

The LabJack evaluates each software interlock once per acquisition cycle at 20 Hz. Any trip
drives DAC0 to 0 V, removing the SSR gate voltage by the same path as a hardware
discontinuity, and latches the system into a FAULT state requiring an operator reset.

Because the sampling interval is 50 ms, these interlocks cannot respond to microsecond-scale
transients. They provide orderly shutdown, annunciation, and an attributable fault record.
Transient overcurrent protection is provided by the hardware comparator in §7.3.

The Interlock Readback becomes valid 0.6 s after enable. Node X is the gate voltage measured
downstream of the switch chain, so it reads low whenever the gate is down, irrespective of
switch state.
