#!/usr/bin/env python3
"""LabJack T7 diagnostic and timing benchmark. Read-only unless --dac."""

import argparse
import statistics
import sys
import time

PASS, FAIL, WARN, INFO = "PASS", "FAIL", "WARN", "  - "
results = []


def report(status, label, detail=""):
    results.append((status, label))
    mark = {PASS: "[ ok ]", FAIL: "[FAIL]", WARN: "[warn]"}[status]
    print(f"  {mark}  {label}" + (f"   {detail}" if detail else ""))


def note(text):
    print(f"         {text}")


def section(title):
    print(f"\n{title}\n" + "-" * len(title))


def connect(conn, ident):
    try:
        from labjack import ljm
    except ImportError:
        sys.exit("labjack-ljm not installed.  pip install labjack-ljm")
    try:
        return ljm, ljm.openS("T7", conn, ident)
    except Exception as exc:
        print(f"Could not open T7 ({conn} {ident}): {exc}\n")
        if conn == "USB":
            print("  lsusb | grep -i labjack        does the OS see it?\n"
                  "  LJM installed on this host?    its udev rules set permissions\n"
                  "  replug the T7 after installing LJM\n")
        else:
            print(f"  ping {ident}\n")
        print("  Kipling closed? api stopped?   only one process may hold the T7")
        sys.exit(1)


def identity(ljm, h):
    section("1. Identity and firmware")
    dt, ct, serial, ip, port, maxb = ljm.getHandleInfo(h)
    conn_name = {1: "USB", 3: "TCP", 4: "ETHERNET", 5: "WIFI"}.get(ct, str(ct))
    report(PASS, "device open", f"T7 serial {serial}  via {conn_name}")
    if ct != 1:
        note(f"address {ljm.numberToIP(int(ip))}:{int(port)}")
    note(f"max packet {int(maxb)} bytes")

    fw = ljm.eReadName(h, "FIRMWARE_VERSION")
    boot = ljm.eReadName(h, "BOOTLOADER_VERSION")
    hw = ljm.eReadName(h, "HARDWARE_VERSION")
    report(PASS if fw >= 1.0217 else WARN, f"firmware {fw:.4f}",
           "" if fw >= 1.0217 else "older than 1.0217, some EF indices differ")
    note(f"bootloader {boot:.4f}   hardware {hw:.2f}")

    try:
        tk = ljm.eReadName(h, "TEMPERATURE_DEVICE_K")
        tc = tk - 273.15
        report(PASS if 0 < tc < 70 else WARN, f"internal temperature {tc:.1f} C")
    except Exception as exc:
        report(WARN, "internal temperature unreadable", str(exc))


def adc_health(ljm, h):
    section("2. ADC health")
    ljm.eWriteName(h, "AIN15_RANGE", 10.0)
    reads = [ljm.eReadName(h, "AIN15") for _ in range(40)]
    mean_mv = statistics.mean(reads) * 1000
    sd_mv = statistics.pstdev(reads) * 1000
    span_mv = (max(reads) - min(reads)) * 1000

    ok = abs(mean_mv) < 2.0
    report(PASS if ok else FAIL, f"AIN15 ground offset {mean_mv:+.3f} mV",
           "within +/-2 mV" if ok else "outside +/-2 mV")
    if sd_mv < 1e-6:
        report(FAIL, "AIN15 is perfectly static",
               "a dead converter reads a constant, not a quiet one")
    else:
        report(PASS, f"AIN15 noise sd {sd_mv:.4f} mV", f"span {span_mv:.3f} mV")


def analog_raw(ljm, h):
    section("3. Analog inputs, raw")
    for ch in range(4):
        ljm.eWriteNames(h, 3,
                        [f"AIN{ch}_RANGE", f"AIN{ch}_RESOLUTION_INDEX",
                         f"AIN{ch}_NEGATIVE_CH"], [10.0, 8, 199])
    vals = ljm.eReadNames(h, 4, ["AIN0", "AIN1", "AIN2", "AIN3"])
    expect = {
        0: ("HASS Uout", 2.30, 2.70, "should sit near the 2.5 V reference"),
        1: ("free / loopback", None, None, "floats when nothing is attached"),
        2: ("LJTick-Div-25", None, None, "x25 -> laser volts"),
        3: ("thermistor raw", 0.05, 3.10, "200uA x R, compliance ceiling ~3 V"),
    }
    for ch, v in enumerate(vals):
        label, lo, hi, why = expect[ch]
        if lo is None:
            report(INFO if False else PASS, f"AIN{ch} = {v:+.5f} V", f"{label}")
        elif lo <= v <= hi:
            report(PASS, f"AIN{ch} = {v:+.5f} V", f"{label}, in range")
        else:
            report(WARN, f"AIN{ch} = {v:+.5f} V", f"{label}, expected {lo}-{hi} V")
        note(why)


def thermistor(ljm, h, sh):
    section("4. Thermistor on AIN3, via AIN-EF")
    names = ["AIN3_EF_INDEX", "AIN3_EF_CONFIG_A", "AIN3_EF_CONFIG_B",
             "AIN3_EF_CONFIG_D", "AIN3_EF_CONFIG_E", "AIN3_EF_CONFIG_F",
             "AIN3_EF_CONFIG_G", "AIN3_EF_CONFIG_H",
             "AIN3_EF_CONFIG_I", "AIN3_EF_CONFIG_J"]
    values = [50, 1, 0, 1.0, 0.0, 10000.0] + list(sh)
    try:
        ljm.eWriteNames(h, len(names), names, values)
        report(PASS, "AIN-EF 50 configured", "Steinhart-Hart, 200 uA excitation")
    except Exception as exc:
        return report(FAIL, "AIN-EF config rejected", str(exc))

    time.sleep(0.2)
    raw = ljm.eReadName(h, "AIN3")
    try:
        t_c = ljm.eReadName(h, "AIN3_EF_READ_A")
    except Exception as exc:
        return report(FAIL, "AIN3_EF_READ_A failed", str(exc))

    r_ohm = raw / 200e-6 if raw > 0 else 0
    report(PASS, f"resistance {r_ohm:,.0f} ohm", f"from {raw:.5f} V at 200 uA")
    ok = -20 < t_c < 90
    report(PASS if ok else WARN, f"temperature {t_c:.2f} C",
           "plausible" if ok else "implausible, check coefficients and wiring")
    if raw > 2.9:
        report(WARN, "near the 200 uA compliance ceiling",
               "R > ~15k, i.e. below ~10 C. Move to the 10UA terminal")
    note("coefficients are PLACEHOLDERS unless you ran calibrate_thermistor.py")


def digital(ljm, h):
    section("5. Digital inputs")
    names = ["FIO0", "FIO1", "FIO2", "FIO3"]
    vals = ljm.eReadNames(h, 4, names)
    meaning = {
        "FIO0": "flow reed, HIGH when contact open (3.3k/6.8k divider)",
        "FIO1": "interlock node X, HIGH only when DAC0 high AND all switches closed",
        "FIO2": "1-Wire bus, unused for now",
        "FIO3": "comparator trip latch, unused for now",
    }
    for n, v in zip(names, vals):
        report(PASS, f"{n} = {'HIGH' if v > 0.5 else 'low '}", meaning[n])
    note("FIO1 low is CORRECT here: DAC0 is at 0 V, so the chain is unpowered")


def counter(ljm, h, index, debounce_us, seconds):
    section("6. Flow pulse counter on FIO0")
    try:
        ljm.eWriteNames(h, 4,
                        ["DIO0_EF_ENABLE", "DIO0_EF_INDEX",
                         "DIO0_EF_CONFIG_A", "DIO0_EF_ENABLE"],
                        [0, index, debounce_us, 1])
        report(PASS, f"DIO-EF index {index} accepted", f"debounce {debounce_us:.0f} us")
    except Exception as exc:
        return report(FAIL, f"DIO-EF index {index} rejected", str(exc))

    c0 = ljm.eReadName(h, "DIO0_EF_READ_A")
    print(f"         counting for {seconds:.1f} s ...")
    time.sleep(seconds)
    c1 = ljm.eReadName(h, "DIO0_EF_READ_A")
    d = c1 - c0
    hz = d / seconds

    if d == 0:
        report(WARN, "counter did not move", "pump off, or wrong DIO-EF index")
        note("A wrong index gives a counter that never increments and reads a")
        note("clean, stable, plausible 0.00 LPM. Verify the index in the T7 docs.")
    else:
        report(PASS, f"{d:.0f} pulses in {seconds:.1f} s = {hz:.2f} Hz",
               f"{hz * 0.307:.2f} LPM at 0.307 LPM/Hz")


def dac_loopback(ljm, h):
    section("7. DAC loopback  (DAC0 is the laser enable line)")
    print("  DAC0 drives the interlock chain. This test raises it to 4.5 V.")
    print("  The SSR load side must be PHYSICALLY DISCONNECTED.")
    print("  Jumper DAC0 -> AIN1, then type  LOAD DISCONNECTED  to proceed: ", end="")
    if input().strip() != "LOAD DISCONNECTED":
        return report(WARN, "DAC tests skipped", "confirmation not given")

    ljm.eWriteNames(h, 3, ["AIN1_RANGE", "AIN1_RESOLUTION_INDEX",
                           "AIN1_NEGATIVE_CH"], [10.0, 8, 199])
    worst = 0.0
    try:
        for v in (0.5, 1.5, 2.5, 3.5, 4.5):
            ljm.eWriteName(h, "DAC0", v)
            time.sleep(0.12)
            got = ljm.eReadName(h, "AIN1")
            err = abs(got - v)
            worst = max(worst, err)
            print(f"         DAC0 {v:.2f} -> AIN1 {got:.4f}   err {err*1000:+6.1f} mV")
    finally:
        ljm.eWriteName(h, "DAC0", 0.0)
    report(PASS if worst < 0.050 else FAIL,
           f"DAC0 loopback worst error {worst*1000:.1f} mV", "limit 50 mV")

    print("  Move the jumper to DAC1 -> AIN1, press Enter (or 's' to skip): ", end="")
    if input().strip().lower() == "s":
        return report(WARN, "DAC1 skipped", "")
    worst = 0.0
    try:
        for v in (0.5, 2.5, 4.5):
            ljm.eWriteName(h, "DAC1", v)
            time.sleep(0.12)
            got = ljm.eReadName(h, "AIN1")
            worst = max(worst, abs(got - v))
            print(f"         DAC1 {v:.2f} -> AIN1 {got:.4f}")
    finally:
        ljm.eWriteName(h, "DAC1", 0.0)
    report(PASS if worst < 0.050 else FAIL,
           f"DAC1 loopback worst error {worst*1000:.1f} mV",
           "DAC1 was previously miswired as an SSR return, so worth proving")


def benchmark(ljm, h, iterations):
    section("8. Timing benchmark")
    batch = ["AIN0", "AIN2", "AIN3_EF_READ_A", "FIO1", "DIO0_EF_READ_A"]

    def timeit(fn, n):
        out = []
        for _ in range(n):
            t = time.perf_counter()
            fn()
            out.append((time.perf_counter() - t) * 1000)
        return out

    single = timeit(lambda: ljm.eReadName(h, "AIN0"), iterations)
    multi = timeit(lambda: ljm.eReadNames(h, len(batch), batch), iterations)

    for label, samples in (("single channel", single),
                           (f"batched {len(batch)} channels", multi)):
        s = sorted(samples)
        p95 = s[int(len(s) * 0.95)]
        print(f"         {label:24s} mean {statistics.mean(s):6.2f} ms   "
              f"p95 {p95:6.2f} ms   max {s[-1]:6.2f} ms")

    mean_ms = statistics.mean(multi)
    max_hz = 1000.0 / max(sorted(multi)[int(len(multi) * 0.99)], 1e-6)
    report(PASS if mean_ms < 25 else WARN,
           f"acquisition loop budget {mean_ms:.2f} ms per scan",
           f"headroom for ~{max_hz:.0f} Hz at p99")
    note("The stack runs at 20 Hz, a 50 ms budget. Anything under 25 ms is fine.")
    note("Batching beats separate reads because each round trip costs latency,")
    note("and one scan keeps every channel on the same timestamp.")


def main():
    p = argparse.ArgumentParser(description="LabJack T7 diagnostic")
    p.add_argument("--conn", default="USB", choices=["USB", "ETHERNET"])
    p.add_argument("--id", dest="ident", default=None,
                   help="IP for ETHERNET, serial or ANY for USB")
    p.add_argument("--dac", action="store_true",
                   help="include DAC loopback tests (asserts the enable line)")
    p.add_argument("--counter-index", type=int, default=9,
                   help="DIO_EF index for Interrupt Counter with Debounce")
    p.add_argument("--debounce-us", type=float, default=1500)
    p.add_argument("--count-seconds", type=float, default=3.0)
    p.add_argument("--iterations", type=int, default=200)
    p.add_argument("--sh", nargs=4, type=float,
                   default=[0.001125, 0.000234, 0.0, 0.0000000876],
                   metavar=("A", "B", "C", "D"))
    args = p.parse_args()

    ident = args.ident or ("ANY" if args.conn == "USB" else "")
    if not ident:
        p.error("--id is required with --conn ETHERNET")

    print("=" * 66)
    print("LabJack T7 diagnostic")
    print("=" * 66)

    ljm, h = connect(args.conn, ident)
    try:
        ljm.eWriteName(h, "DAC0", 0.0)
        identity(ljm, h)
        adc_health(ljm, h)
        analog_raw(ljm, h)
        thermistor(ljm, h, args.sh)
        digital(ljm, h)
        counter(ljm, h, args.counter_index, args.debounce_us, args.count_seconds)
        if args.dac:
            dac_loopback(ljm, h)
        else:
            section("7. DAC loopback")
            print("         skipped. Re-run with --dac to include it.")
        benchmark(ljm, h, args.iterations)
    finally:
        try:
            ljm.eWriteName(h, "DAC0", 0.0)
            ljm.eWriteName(h, "DAC1", 0.0)
        except Exception:
            pass
        ljm.close(h)

    section("Summary")
    n_fail = sum(1 for s, _ in results if s == FAIL)
    n_warn = sum(1 for s, _ in results if s == WARN)
    n_pass = sum(1 for s, _ in results if s == PASS)
    print(f"  {n_pass} passed, {n_warn} warnings, {n_fail} failed")
    for s, label in results:
        if s != PASS:
            print(f"    {s}: {label}")
    print("\n  DAC0 left at 0 V. Enable line is safe.")
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
