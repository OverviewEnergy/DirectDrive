#!/usr/bin/env python3
"""Fit Steinhart-Hart coefficients from measured R-T points."""

import argparse
import math
import sys

KELVIN = 273.15


def solve(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    """Gaussian elimination with partial pivoting. Small system (3x3 or 4x4), so plain"""
    n = len(matrix)
    a = [row[:] + [rhs[i]] for i, row in enumerate(matrix)]

    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[piv][col]) < 1e-18:
            raise ValueError(
                "singular system -- your calibration points are too close together "
                "or duplicated. Spread them further apart."
            )
        a[col], a[piv] = a[piv], a[col]
        for r in range(col + 1, n):
            f = a[r][col] / a[col][col]
            for c in range(col, n + 1):
                a[r][c] -= f * a[col][c]

    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        s = a[r][n] - sum(a[r][c] * x[c] for c in range(r + 1, n))
        x[r] = s / a[r][r]
    return x


def fit(points: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    """Fit Steinhart-Hart to (temperature_C, resistance_ohms) points"""
    n = len(points)
    if n not in (3, 4):
        raise ValueError("need exactly 3 or 4 calibration points")

    rows, rhs = [], []
    for t_c, r_ohm in points:
        if r_ohm <= 0:
            raise ValueError(f"resistance must be positive, got {r_ohm}")
        L = math.log(r_ohm)
        rhs.append(1.0 / (t_c + KELVIN))
        if n == 3:
            rows.append([1.0, L, L ** 3])          # classic: no squared term
        else:
            rows.append([1.0, L, L ** 2, L ** 3])  # full four-term

    sol = solve(rows, rhs)
    if n == 3:
        A, B, C3 = sol
        return A, B, 0.0, C3     # squared term is zero; cubic goes in the D slot
    return tuple(sol)


def temp_c(A: float, B: float, C: float, D: float, r_ohm: float) -> float:
    L = math.log(r_ohm)
    return 1.0 / (A + B * L + C * L**2 + D * L**3) - KELVIN


def report(points, coeffs):
    A, B, C, D = coeffs
    print("\n=== COEFFICIENTS ===")
    print(f"  A = {A:.10e}      -> AIN1_EF_CONFIG_G")
    print(f"  B = {B:.10e}      -> AIN1_EF_CONFIG_H")
    print(f"  C = {C:.10e}      -> AIN1_EF_CONFIG_I")
    print(f"  D = {D:.10e}      -> AIN1_EF_CONFIG_J")

    print("\n=== FIT CHECK (should be near-exact at the calibration points) ===")
    worst = 0.0
    for t_c, r in sorted(points):
        got = temp_c(*coeffs, r)
        err = got - t_c
        worst = max(worst, abs(err))
        print(f"  {r:9.1f} ohm   measured {t_c:6.2f} C   model {got:6.2f} C   "
              f"err {err:+.3f} C")
    print(f"  worst residual: {worst:.4f} C")
    if worst > 0.05:
        print("  WARNING: residual is large for an exact fit. Check your R and T numbers.")

    print("\n=== EXTRAPOLATION SANITY (outside your points -- treat with suspicion) ===")
    for r in (50000, 32000, 20000, 15000, 10000, 5000, 2500, 1000):
        t = temp_c(*coeffs, r)
        # 200 uA * R must stay under ~3 V.
        v = 200e-6 * r
        note = ""
        if v >= 3.0:
            note = f"  <-- {v:.2f} V exceeds 200uA compliance, use the 10UA source here"
        print(f"  {r:9.0f} ohm -> {t:7.2f} C{note}")

    print("\n=== APPLY ===")
    print("In .env or docker-compose.yml:")
    print(f"  SH_A={A:.10e}")
    print(f"  SH_B={B:.10e}")
    print(f"  SH_C={C:.10e}")
    print(f"  SH_D={D:.10e}")
    print("\nOr for a bring-up run:")
    print(f"  python3 bringup.py --ip <ip> --sh {A:.10e} {B:.10e} {C:.10e} {D:.10e}")


def selftest():
    """Verify the solver by round-tripping known coefficients: generate synthetic R-T data"""
    print("=== SELF-TEST ===\n")
    ok = True

    trueA, trueB, trueD = 1.129241e-3, 2.341077e-4, 8.775468e-8
    pts = []
    for r in (32650.0, 12490.0, 4160.0):
        L = math.log(r)
        t = 1.0 / (trueA + trueB * L + trueD * L**3) - KELVIN
        pts.append((t, r))
    A, B, C, D = fit(pts)
    e = max(abs(A - trueA), abs(B - trueB), abs(D - trueD))
    print(f"3-point (classic 3-term):")
    print(f"  true  A={trueA:.6e} B={trueB:.6e} C=0 D={trueD:.6e}")
    print(f"  fit   A={A:.6e} B={B:.6e} C={C:.1e} D={D:.6e}")
    print(f"  max coefficient error {e:.2e}  -> {'PASS' if e < 1e-12 else 'FAIL'}")
    ok &= e < 1e-12

    t4 = (1.1e-3, 2.3e-4, 1.5e-7, 8.5e-8)
    pts4 = []
    for r in (40000.0, 20000.0, 8000.0, 3000.0):
        L = math.log(r)
        t = 1.0 / (t4[0] + t4[1]*L + t4[2]*L**2 + t4[3]*L**3) - KELVIN
        pts4.append((t, r))
    f4 = fit(pts4)
    e4 = max(abs(a - b) for a, b in zip(f4, t4))
    print(f"\n4-point (full 4-term, nonzero C):")
    print(f"  true  {' '.join(f'{v:.4e}' for v in t4)}")
    print(f"  fit   {' '.join(f'{v:.4e}' for v in f4)}")
    print(f"  max coefficient error {e4:.2e}  -> {'PASS' if e4 < 1e-10 else 'FAIL'}")
    ok &= e4 < 1e-10

    print("\nDegenerate input (duplicate points):")
    try:
        fit([(25.0, 10000.0), (25.0, 10000.0), (50.0, 4000.0)])
        print("  no error raised -> FAIL")
        ok = False
    except ValueError as ex:
        print(f"  correctly rejected: {ex}")

    print("\nRealistic 10k NTC, beta=3950, 0/25/50 C:")
    B25 = 3950.0
    real = []
    for t in (0.0, 25.0, 50.0):
        r = 10000.0 * math.exp(B25 * (1.0/(t+KELVIN) - 1.0/298.15))
        real.append((t, r))
        print(f"  {t:5.1f} C -> {r:9.1f} ohm")
    cf = fit(real)
    worst = max(abs(temp_c(*cf, r) - t) for t, r in real)
    print(f"  fit residual at calibration points: {worst:.6f} C -> "
          f"{'PASS' if worst < 1e-6 else 'FAIL'}")
    ok &= worst < 1e-6

    print(f"\n{'ALL TESTS PASS' if ok else 'SOME TESTS FAILED'}")
    return 0 if ok else 1


def main():
    p = argparse.ArgumentParser(description="Steinhart-Hart coefficients from R-T points")
    p.add_argument("--point", nargs=2, type=float, action="append",
                   metavar=("TEMP_C", "RESISTANCE_OHM"),
                   help="a measured pair; give this 3 or 4 times")
    p.add_argument("--selftest", action="store_true", help="verify the solver")
    args = p.parse_args()

    if args.selftest:
        sys.exit(selftest())
    if not args.point or len(args.point) not in (3, 4):
        p.error("give --point exactly 3 or 4 times (or use --selftest)")

    points = [(t, r) for t, r in args.point]
    print("Calibration points:")
    for t, r in sorted(points):
        print(f"  {t:6.2f} C  ->  {r:9.1f} ohm")
    report(points, fit(points))


if __name__ == "__main__":
    main()
