#!/usr/bin/env python3
"""Ophir discovery: USB enumeration, snapshot diff, serial ports, live read."""

import argparse
import json
import os
import platform
import re
import subprocess
import sys
import time

SNAPSHOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "usb_snapshot.json")
HINTS = re.compile(r"ophir|juno|starlab|nova|vega|pd300|thermopile", re.I)


def head(title):
    print(f"\n{title}\n" + "-" * len(title))


def usb_devices() -> list[str]:
    system = platform.system()
    try:
        if system == "Linux":
            out = subprocess.run(["lsusb"], capture_output=True, text=True,
                                 timeout=10).stdout
            return [l.strip() for l in out.splitlines() if l.strip()]
        if system == "Windows":
            ps = ("Get-PnpDevice -PresentOnly | "
                  "Where-Object {$_.InstanceId -like 'USB*'} | "
                  "Select-Object -ExpandProperty FriendlyName")
            out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                                 capture_output=True, text=True, timeout=30).stdout
            return sorted({l.strip() for l in out.splitlines() if l.strip()})
        if system == "Darwin":
            out = subprocess.run(["system_profiler", "SPUSBDataType"],
                                 capture_output=True, text=True, timeout=30).stdout
            return [l.strip() for l in out.splitlines() if l.strip().endswith(":")]
    except FileNotFoundError:
        print("  enumeration tool not found on this platform")
    except subprocess.TimeoutExpired:
        print("  enumeration timed out")
    return []


def serial_ports() -> list[tuple[str, str]]:
    try:
        from serial.tools import list_ports
    except ImportError:
        print("  pyserial not installed, skipping.  pip install pyserial")
        return []
    return [(p.device, f"{p.description} [{p.hwid}]") for p in list_ports.comports()]


def try_com():
    """Ophir's OphirLMMeasurement COM object. Windows + StarLab only."""
    head("Ophir COM object (Windows, StarLab installed)")
    if platform.system() != "Windows":
        print("  not Windows, skipped")
        return False
    try:
        import win32com.client
    except ImportError:
        print("  pywin32 not installed.  py -m pip install pywin32")
        return False
    try:
        com = win32com.client.Dispatch("OphirLMMeasurement.CoLMMeasurement")
    except Exception as exc:
        print(f"  [FAIL] cannot create the COM object: {exc}")
        print("         StarLab is not installed, or it did not register the object.")
        print("         Install StarLab from ophiropt.com and try again.")
        return False
    print("  [ ok ] COM object created")

    try:
        serials = com.ScanUSB()
    except Exception as exc:
        print(f"  [FAIL] ScanUSB failed: {exc}")
        return False
    if not serials:
        print("  [warn] COM object works but no USB device found.")
        print("         Check the cable and that StarLab itself is CLOSED.")
        return False
    print(f"  [ ok ] devices found: {list(serials)}")

    handle = None
    try:
        handle = com.OpenUSBDevice(serials[0])
        print(f"  [ ok ] opened {serials[0]}")
        for ch in range(4):
            try:
                exists, name, stype = com.GetSensorInfo(handle, ch)
            except Exception:
                break
            if not exists:
                continue
            print(f"         channel {ch}: {name}  type {stype}")
        com.StartStream(handle, 0)
        print("  [ ok ] stream started, sampling 3 s ...")
        got = 0
        for _ in range(30):
            time.sleep(0.1)
            data = com.GetData(handle, 0)
            if data and data[0]:
                for value, ts, stat in zip(*data):
                    got += 1
                    if got <= 5:
                        print(f"         {value:.4f} W   t={ts}   status={stat}")
        com.StopStream(handle, 0)
        if got:
            print(f"  [ ok ] {got} samples read. The meter works.")
            return True
        print("  [warn] stream started but returned no samples.")
        print("         Sensor may be unplugged from the Juno, or set to a bad range.")
    except Exception as exc:
        print(f"  [FAIL] read failed: {exc}")
    finally:
        if handle is not None:
            try:
                com.Close(handle)
            except Exception:
                pass
    return False


def main():
    p = argparse.ArgumentParser(description="Ophir discovery")
    p.add_argument("--snapshot", action="store_true",
                   help="save the current USB device list, with the Juno UNPLUGGED")
    p.add_argument("--no-com", action="store_true", help="skip the COM attempt")
    args = p.parse_args()

    print("=" * 66)
    print(f"Ophir discovery   host: {platform.system()} {platform.machine()}")
    print("=" * 66)

    devices = usb_devices()

    if args.snapshot:
        with open(SNAPSHOT, "w") as fh:
            json.dump(devices, fh, indent=1)
        print(f"\nSaved {len(devices)} USB devices to {os.path.basename(SNAPSHOT)}")
        print("Now plug the Juno in, wait 5 s, and run without --snapshot.")
        return 0

    head(f"USB devices ({len(devices)})")
    for d in devices:
        print(f"  {'>>' if HINTS.search(d) else '  '} {d}")

    matched = [d for d in devices if HINTS.search(d)]
    if matched:
        print(f"\n  [ ok ] {len(matched)} device(s) matched an Ophir-ish name")
    else:
        print("\n  [warn] nothing matched by name. That does not mean it is absent:")
        print("         Ophir hardware often enumerates under a generic USB name.")
        print("         Use the snapshot diff below to identify it by elimination.")

    if os.path.exists(SNAPSHOT):
        head("Diff against snapshot")
        with open(SNAPSHOT) as fh:
            before = json.load(fh)
        added = [d for d in devices if d not in before]
        removed = [d for d in before if d not in devices]
        if added:
            print("  APPEARED since the snapshot, one of these is the Juno:")
            for d in added:
                print(f"    + {d}")
        else:
            print("  Nothing new appeared.")
            print("  The Juno is not connected to THIS machine, the cable is dead,")
            print("  or it needs external power. Check for a power LED on the box.")
        for d in removed:
            print(f"    - {d}   (gone)")
    else:
        head("No snapshot yet")
        print("  Unplug the Juno, run:   python3 check_ophir.py --snapshot")
        print("  Then plug it in and run this again. The diff names the device.")

    head("Serial ports")
    ports = serial_ports()
    if ports:
        for dev, desc in ports:
            print(f"  {'>>' if HINTS.search(desc) else '  '} {dev}   {desc}")
        print("\n  If the Juno shows here, it speaks serial and you can talk to it")
        print("  from the Pi directly with app/ophir.py, no Windows needed.")
    else:
        print("  none found")

    if not args.no_com:
        try_com()

    head("What to do next")
    system = platform.system()
    if system == "Windows":
        print("  If the COM section passed, run bridge/bridge.py here and point it")
        print("  at the Pi:")
        print("      set STAND_URL=http://10.1.0.52:8000")
        print("      py bridge.py --backend com")
    else:
        print("  The Juno's normal driver is Windows-only, so on Linux you have")
        print("  three options:")
        print("    1. Run bridge/bridge.py on the Windows laptop (works today)")
        print("    2. If it appeared as a serial port above, use app/ophir.py")
        print("       with OPHIR_PORT set, and drop the laptop entirely")
        print("    3. Ask Ophir for the Linux USB beta package, which removes")
        print("       the laptop and the whole two-clock sync problem")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
