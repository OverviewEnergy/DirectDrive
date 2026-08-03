#!/usr/bin/env python3
"""Enumerate DS18B20 ROM addresses and print an ONEWIRE_ROLES line for .env."""

import argparse
import sys

FUNC_SEARCH = 0xF0
ROLES = ["t_module", "t_coolant_in", "t_coolant_out", "t_ambient"]


def scan(handle, ljm, dionum: int, limit: int = 16) -> list[int]:
    ljm.eWriteNames(handle, 3,
                    ["ONEWIRE_DQ_DIONUM", "ONEWIRE_DPU_DIONUM", "ONEWIRE_OPTIONS"],
                    [dionum, 0, 0])
    found, path = [], 0
    for _ in range(limit):
        ljm.eWriteNames(handle, 6,
                        ["ONEWIRE_PATH_H", "ONEWIRE_PATH_L", "ONEWIRE_FUNCTION",
                         "ONEWIRE_NUM_BYTES_TX", "ONEWIRE_NUM_BYTES_RX",
                         "ONEWIRE_GO"],
                        [(path >> 32) & 0xFFFFFFFF, path & 0xFFFFFFFF,
                         FUNC_SEARCH, 0, 0, 1])
        rh, rl, bh, bl = ljm.eReadNames(
            handle, 4,
            ["ONEWIRE_SEARCH_RESULT_H", "ONEWIRE_SEARCH_RESULT_L",
             "ONEWIRE_ROM_BRANCHS_FOUND_H", "ONEWIRE_ROM_BRANCHS_FOUND_L"])
        rom = (int(rh) << 32) | int(rl)
        if rom and rom not in found:
            found.append(rom)
        path = (int(bh) << 32) | int(bl)
        if path == 0:
            break
    return found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ip", default="192.168.2.2")
    ap.add_argument("--dionum", type=int, default=2, help="FIO number carrying DQ")
    args = ap.parse_args()

    from labjack import ljm
    handle = ljm.openS("T7", "ETHERNET", args.ip)
    try:
        roms = scan(handle, ljm, args.dionum)
    finally:
        ljm.close(handle)

    if not roms:
        print("no devices found on FIO%d" % args.dionum, file=sys.stderr)
        return 1

    print("found %d device(s):" % len(roms))
    for i, rom in enumerate(roms):
        family = rom & 0xFF
        note = "" if family == 0x28 else "  <- not a DS18B20 (family 0x28)"
        print("  %d  %016X%s" % (i, rom, note))

    pairs = ["%s:%016X" % (ROLES[i], rom)
             for i, rom in enumerate(roms) if i < len(ROLES)]
    print("\nPaste into .env, then reassign roles to match physical placement:")
    print("ONEWIRE_ROLES=" + ",".join(pairs))
    print("ONEWIRE_ENABLED=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
