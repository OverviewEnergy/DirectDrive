#!/usr/bin/env bash
# One-time host setup for the api + tools. Run from the repo root.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

echo "== python venv =="
python3 -m venv .venv
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -q -r requirements.txt

echo "== .env =="
[ -f .env ] || cp .env.example .env

echo "== check LJM =="
if ! .venv/bin/python -c "from labjack import ljm" 2>/dev/null; then
  echo "  labjack-ljm imported but the native LJM library is MISSING."
  echo "  Install it, then re-run this script:"
  echo "    https://support.labjack.com/docs/ljm-software-installer-downloads-t4-t7-t8-digit"
  echo "    uname -m says: $(uname -m)"
  exit 1
fi
echo "  ok"

echo "== systemd unit =="
sudo cp install/leolaser-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable leolaser-api

echo
echo "Done. Now:"
echo "  docker compose up -d          # influxdb + grafana"
echo "  sudo systemctl start leolaser-api"
echo "  curl -s localhost:8000/health"
