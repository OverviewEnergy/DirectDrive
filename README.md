# PV Direct-Drive Laser Test Stand

Driving an nLight n24i laser diode directly from a photovoltaic array, with no laser diode
driver in the circuit.

A laser diode is normally fed by a driver that regulates current, ramps softly, and clamps
faults. This stand removes it. The operating point is set by the intersection of the panel's
IV curve and the diode's IV curve, and irradiance is the only control input.

It works because a PV panel operated well below its maximum power point behaves as a stiff
current source, which is what a laser diode wants. It is dangerous because that intersection
has no active clamp, and catastrophic optical damage develops in microseconds.


Predicted operating point

Two Renogy RNG-320D in series, label values Voc 80.6 V, Vmp 66.0 V, Isc 10.23 A, Imp 9.70 A.

| | Value |
|---|---|
| Diode voltage | 38.5 to 39.5 V, set by the diode |
| Array current | **10.23 A**, Isc|
| Electrical in | 399 W |
| Optical out | ~190 W |
| Array MPP, for comparison | 642 W at 67.4 V |

At 39 V the string sits at 58% of Vmp, deep in the current-source region: current varies by
0.0007 A across the whole 38.0 to 39.5 V band. The diode pins the voltage, the panel sets
the current, and neither can push the other around.


