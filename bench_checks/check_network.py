#!/usr/bin/env python3
"""Network and service reachability. Use --host from a remote machine."""

import argparse
import json
import platform
import socket
import subprocess
import sys
import urllib.error
import urllib.request

SERVICES = [("api", 8000, "/status"), ("influxdb", 8086, "/ping"),
            ("grafana", 3000, "/api/health")]


def head(t):
    print(f"\n{t}\n" + "-" * len(t))


def ping(host):
    flag = "-n" if platform.system() == "Windows" else "-c"
    try:
        r = subprocess.run(["ping", flag, "2", host], capture_output=True,
                           text=True, timeout=15)
        return r.returncode == 0
    except Exception:
        return False


def port_open(host, port, timeout=2.0):
    try:
        with socket.create_connection((host, port), timeout):
            return True
    except OSError:
        return False


def http(url, timeout=4.0):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read(4000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return None, str(e)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="localhost")
    p.add_argument("--labjack", default=None, help="T7 IP, if on ETHERNET")
    args = p.parse_args()

    print("=" * 66)
    print(f"Stack reachability   target {args.host}")
    print("=" * 66)

    head("Reachability")
    if args.host not in ("localhost", "127.0.0.1"):
        print(f"  ping {args.host}: {'ok' if ping(args.host) else 'FAILED'}")
    if args.labjack:
        print(f"  ping {args.labjack} (T7): "
              f"{'ok' if ping(args.labjack) else 'FAILED'}")
        print(f"  modbus 502 open: "
              f"{'yes' if port_open(args.labjack, 502) else 'no'}")

    head("Services")
    for name, port, path in SERVICES:
        if not port_open(args.host, port):
            print(f"  [FAIL] {name:9s} :{port} closed")
            continue
        code, body = http(f"http://{args.host}:{port}{path}")
        ok = code in (200, 204)
        print(f"  [{'ok' if ok else 'warn'}] {name:9s} :{port} -> HTTP {code}")
        if name == "api" and ok:
            try:
                d = json.loads(body)
                print(f"         state {d['state']}  mode {d['mode']}  "
                      f"source {d['source']}")
            except Exception:
                pass

    head("API health")
    code, body = http(f"http://{args.host}:8000/health")
    if code != 200:
        print(f"  api not answering /health (HTTP {code})")
        return 1
    d = json.loads(body)
    for k in ["influx_reachable", "points_written", "write_errors", "loop_dt_s",
              "loop_overruns", "source_errors", "onewire_enabled"]:
        print(f"  {k:20s} {d.get(k)}")
    opt = d.get("optical", {})
    if opt:
        print(f"  optical received      {opt.get('received')}")
        print(f"  optical external      {opt.get('external_samples')}")
    if not d.get("influx_reachable"):
        print("\n  influx_reachable is false. Wait 20 s after first start, then retry.")
        print("  If it stays false, check INFLUX_URL in .env: it must be")
        print("  http://localhost:8086 when the api runs on the host.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
