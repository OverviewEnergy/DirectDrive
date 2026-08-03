#!/usr/bin/env python3
"""T7 bring-up: self-test, interlock test, HASS zero, live monitor. Standalone."""

import argparse
import statistics
import sys
import time

# Keep identical to app/daq.py.
HASS_VREF_V = 2.5
HASS_SENS_V_PER_A = 0.0125
LJTD_RATIO = 25.0
FLOW_LPM_PER_HZ = 0.307


def connect(conn: str, ident: str):
    try:
        from labjack import ljm
    except ImportError:
        sys.exit(
            "LJM Python wrapper not found.\n"
            "  1. Install LabJack's LJM package (native library + udev rules)\n"
            "  2. pip install labjack-ljm"
        )
    try:
        handle = ljm.openS("T7", conn, ident)
    except Exception as e:
        hint = (f"  ping {ident}                    is it reachable at all?\n"
                if conn == "ETHERNET" else
                "  lsusb | grep -i labjack        does the OS see it?\n"
                "  LJM installed on the HOST?     its udev rules set permissions\n"
                "  replug the T7 after installing LJM\n")
        sys.exit(
            f"Could not open T7 ({conn} {ident}): {e}\n\n"
            "Check, in order:\n"
            + hint +
            "  Kipling closed?                only one app can hold the device\n"
            "  sudo systemctl stop leolaser-api   same reason\n"
            "  firmware >= 1.0217             older versions drop static IP on reboot\n"
            "  green+orange LEDs on the jack  both light on an active cable"
        )
    info = ljm.getHandleInfo(handle)
    print(f"Connected: T7  serial {info[2]}  IP {ip}")
    return ljm, handle


def configure(ljm, handle, sh_coeffs):
    """Apply the channel configuration from PINOUT.md."""
    names, values = [], []

    # HASS rides on a 2.5 V offset.
    names += ["AIN0_RANGE", "AIN0_RESOLUTION_INDEX", "AIN0_NEGATIVE_CH"]
    values += [10.0, 8, 199]

    names += ["AIN2_RANGE", "AIN2_RESOLUTION_INDEX", "AIN2_NEGATIVE_CH"]
    values += [10.0, 8, 199]

    names += ["AIN3_EF_INDEX", "AIN3_EF_CONFIG_A", "AIN3_EF_CONFIG_B",
              "AIN3_EF_CONFIG_D", "AIN3_EF_CONFIG_E", "AIN3_EF_CONFIG_F"]
    values += [50, 1, 0, 1.0, 0.0, 10000.0]
    names += ["AIN3_EF_CONFIG_G", "AIN3_EF_CONFIG_H",
              "AIN3_EF_CONFIG_I", "AIN3_EF_CONFIG_J"]
    values += list(sh_coeffs)

    ljm.eWriteNames(handle, len(names), names, values)


def selftest(ljm, handle):
    """LabJack's own AIN/DAC verification, done BEFORE any sensor is attached"""
    print("\n=== SELF-TEST (disconnect all sensors first) ===\n")

    print("1. Ground offset on AIN15 (internally tied to GND):")
    ljm.eWriteName(handle, "AIN15_RANGE", 10.0)
    reads = [ljm.eReadName(handle, "AIN15") for _ in range(20)]
    mean, sd = statistics.mean(reads), statistics.pstdev(reads)
    ok = abs(mean) <= 0.002
    print(f"   mean {mean*1000:+.3f} mV   sd {sd*1e6:.1f} uV")
    print(f"   spec: within +/-2.000 mV   -> {'PASS' if ok else 'FAIL - contact LabJack'}")
    if not all(r == reads[0] for r in reads):
        print("   readings vary (good: a perfectly static value suggests a dead ADC)")

    print("\n2. DAC0 loopback. Jumper DAC0 -> AIN1, then press Enter (or 's' to skip): ", end="")
    if input().strip().lower() == "s":
        print("   skipped")
        return
    ljm.eWriteNames(handle, 3, ["AIN1_RANGE", "AIN1_RESOLUTION_INDEX", "AIN1_NEGATIVE_CH"],
                    [10.0, 8, 199])
    worst = 0.0
    for v in (0.5, 1.5, 2.5, 3.5, 4.5):
        ljm.eWriteName(handle, "DAC0", v)
        time.sleep(0.15)
        got = ljm.eReadName(handle, "AIN1")
        err = abs(got - v)
        worst = max(worst, err)
        print(f"   DAC0 {v:.2f} V -> AIN1 {got:.4f} V   err {err*1000:+.1f} mV")
    ljm.eWriteName(handle, "DAC0", 0.0)
    print(f"   worst error {worst*1000:.1f} mV -> {'PASS' if worst < 0.05 else 'CHECK JUMPER'}")
    print("   DAC0 returned to 0 V. REMOVE THE JUMPER before wiring the interlock.")


def monitor(ljm, handle, turns: int, hass_zero: float, interval: float):
    """Continuous read of every channel, raw beside converted."""
    print("\n=== MONITOR  (Ctrl+C to stop) ===")
    print(f"HASS turns={turns}   zero offset={hass_zero:.4f} V\n")
    print(f"{'AIN0 raw':>10} {'current':>10} | {'AIN2 raw':>10} {'V laser':>10} | "
          f"{'temp':>8} | {'flow Hz':>8} {'LPM':>7} | {'FIO1':>5}")
    print("-" * 90)

    names = ["AIN0", "AIN2", "AIN3_EF_READ_A", "FIO1", "DIO0_EF_READ_A"]
    last_count, last_t = None, None
    try:
        while True:
            t = time.monotonic()
            ain0, ain2, temp_c, fio1, count = ljm.eReadNames(handle, len(names), names)

            current = (ain0 - hass_zero) / (HASS_SENS_V_PER_A * turns)
            v_laser = ain2 * LJTD_RATIO

            hz = 0.0
            if last_count is not None and t > last_t:
                hz = (count - last_count) / (t - last_t)
            last_count, last_t = count, t

            print(f"{ain0:10.5f} {current:9.3f}A | {ain2:10.5f} {v_laser:9.3f}V | "
                  f"{temp_c:7.2f}C | {hz:8.2f} {hz*FLOW_LPM_PER_HZ:7.3f} | "
                  f"{'HIGH' if fio1 > 0.5 else 'low':>5}")
            time.sleep(max(0.0, interval - (time.monotonic() - t)))
    except KeyboardInterrupt:
        print("\nstopped")


def zero_hass(ljm, handle):
    """Measure the HASS zero offset with NO current flowing"""
    print("\n=== HASS ZERO ===")
    print("Confirm NO current is flowing through the sensor window, then press Enter: ", end="")
    input()
    reads = [ljm.eReadName(handle, "AIN0") for _ in range(200)]
    mean, sd = statistics.mean(reads), statistics.pstdev(reads)
    print(f"  measured zero : {mean:.5f} V   (nominal 2.500 V)")
    print(f"  offset error  : {(mean-2.5)*1000:+.2f} mV = "
          f"{(mean-2.5)/HASS_SENS_V_PER_A:+.3f} A of apparent current")
    print(f"  noise (1 sd)  : {sd*1e6:.0f} uV = {sd/HASS_SENS_V_PER_A*1000:.1f} mA")
    print(f"\n  Use --hass-zero {mean:.5f} from now on, and put it in daq.py.")


def interlock_test(ljm, handle):
    """Verify the interlock chain. The most safety-critical step in the whole bring-up"""
    print("\n" + "=" * 70)
    print("INTERLOCK TEST -- THIS ASSERTS THE LASER ENABLE LINE")
    print("=" * 70)
    print("""
Required before continuing:
  [ ] SSR LOAD side physically disconnected (panels AND laser)
  [ ] Breaker open
  [ ] DMM ready to probe node X (the far end of the switch chain)

This raises DAC0 to 5 V so you can confirm each switch breaks the loop.
""")
    if input('Type exactly "LOAD DISCONNECTED" to continue: ').strip() != "LOAD DISCONNECTED":
        print("Aborted. Nothing was energized.")
        return

    try:
        print("\nStep 1: DAC0 = 0 V (baseline)")
        ljm.eWriteName(handle, "DAC0", 0.0)
        time.sleep(0.3)
        print(f"  node X should read ~0 V on your DMM.  FIO1 = "
              f"{'HIGH' if ljm.eReadName(handle,'FIO1') > 0.5 else 'low'}  (expect low)")
        input("  Confirm DMM shows ~0 V, press Enter: ")

        print("\nStep 2: DAC0 = 5 V, ALL switches CLOSED")
        ljm.eWriteName(handle, "DAC0", 5.0)
        time.sleep(0.3)
        print(f"  node X should read ~5 V.  FIO1 = "
              f"{'HIGH' if ljm.eReadName(handle,'FIO1') > 0.5 else 'low'}  (expect HIGH)")
        input("  Confirm DMM shows ~5 V, press Enter: ")

        print("\nStep 3: each switch individually. DAC0 stays at 5 V.")
        for sw in ("KEY switch", "LID switch", "FLOW switch (maintained contact)"):
            input(f"\n  Open the {sw} now, then press Enter: ")
            fio1 = ljm.eReadName(handle, "FIO1")
            state = "HIGH" if fio1 > 0.5 else "low"
            verdict = "PASS" if fio1 <= 0.5 else "*** FAIL - THIS SWITCH DOES NOT BREAK THE LOOP ***"
            print(f"    node X should be ~0 V.  FIO1 = {state}  -> {verdict}")
            input(f"    Close the {sw} again, then press Enter: ")

        print("\nStep 4: power-cycle default")
        print("  Power-cycle the T7 with the load still disconnected, then confirm")
        print("  node X sits at 0 V before any software runs. DAC0 must default to 0 V.")
    finally:
        # De-assert on every exit path.
        ljm.eWriteName(handle, "DAC0", 0.0)
        print("\nDAC0 forced to 0 V. Interlock test complete.")


def main():
    p = argparse.ArgumentParser(description="LabJack T7 hardware bring-up")
    p.add_argument("--conn", default="USB", choices=["USB", "ETHERNET"],
                   help="how the T7 is attached (default USB)")
    p.add_argument("--id", dest="ident", default=None,
                   help="IP for ETHERNET, or serial/ANY for USB (default ANY)")
    p.add_argument("--ip", default=None,
                   help="shorthand for --conn ETHERNET --id <ip>")
    p.add_argument("--hass-turns", type=int, default=1,
                   help="turns of the primary conductor through the HASS window")
    p.add_argument("--hass-zero", type=float, default=HASS_VREF_V,
                   help="measured HASS zero in volts (default nominal 2.5)")
    p.add_argument("--interval", type=float, default=0.5, help="monitor update period, s")
    p.add_argument("--selftest", action="store_true", help="AIN/DAC checks, no sensors")
    p.add_argument("--zero-hass", action="store_true", help="measure the HASS zero offset")
    p.add_argument("--interlock-test", action="store_true",
                   help="verify the interlock chain (asserts the enable line)")
    p.add_argument("--sh", nargs=4, type=float,
                   default=[0.001125, 0.000234, 0.0, 0.0000000876],
                   metavar=("A", "B", "C", "D"),
                   help="Steinhart-Hart coefficients (PLACEHOLDERS by default)")
    args = p.parse_args()

    if args.ip:
        args.conn, args.ident = "ETHERNET", args.ip
    ident = args.ident or ("ANY" if args.conn == "USB" else None)
    if ident is None:
        p.error("--id is required with --conn ETHERNET")
    ljm, handle = connect(args.conn, ident)
    try:
        if args.selftest:
            selftest(ljm, handle)
            return
        configure(ljm, handle, args.sh)
        if args.sh[0] == 0.001125:
            print("NOTE: using PLACEHOLDER Steinhart-Hart coefficients. Temperatures are\n"
                  "      not trustworthy until you run calibrate_thermistor.py.\n")
        if args.zero_hass:
            zero_hass(ljm, handle)
            return
        if args.interlock_test:
            interlock_test(ljm, handle)
            return
        monitor(ljm, handle, args.hass_turns, args.hass_zero, args.interval)
    finally:
        try:
            ljm.eWriteName(handle, "DAC0", 0.0)   # fail safe on every exit path
        except Exception:
            pass
        ljm.close(handle)
        print("Closed. (Restart the API with: docker compose start api)")


if __name__ == "__main__":
    main()
