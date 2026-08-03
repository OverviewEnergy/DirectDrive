# Field Configuration — No External Network

## Topology

```
   T7 ──USB──▶ Pi 5
                 │  wlan0 in ACCESS POINT mode
                 │  SSID: leolaser        Pi: 10.42.0.1
                 ▼
            (WiFi, no router, no internet)
                 ▲
                 │
   Windows laptop, joins leolaser
     bridge.py ──▶ http://10.42.0.1:8000/ingest/optical
     Ophir Juno ──USB──▶ laptop
     browser ──▶ http://10.42.0.1:8000/
```

`eth0` unused. Nothing depends on infrastructure you have to carry, power, or find.

The laptop stays in the loop only because the Juno driver is Windows-only. Everything else
runs on the Pi.

---

## 1. Configure the access point

One time, indoors, while you still have your normal network.

```bash
sudo nmcli con add type wifi ifname wlan0 con-name field-ap \
     autoconnect no ssid leolaser
sudo nmcli con modify field-ap \
     802-11-wireless.mode ap \
     802-11-wireless.band bg \
     ipv4.method shared
sudo nmcli con modify field-ap \
     wifi-sec.key-mgmt wpa-psk \
     wifi-sec.psk "<pick something>"
```

`ipv4.method shared` brings a DHCP server with it, so the laptop just joins and gets an
address. The Pi takes **10.42.0.1**; clients get 10.42.0.2 upward.

`autoconnect no` is deliberate. Without it, `wlan0` gets seized at boot and you lose your
normal WiFi path to the Pi.

`band bg` selects 2.4 GHz. Slower than 5 GHz, considerably better range outdoors, and fewer
regulatory restrictions in AP mode.

### Switching modes

```bash
# go to field
sudo nmcli con up field-ap

# come home
sudo nmcli con down field-ap
sudo nmcli con up "<your-normal-ssid>"
```

**Test both directions indoors before you rely on it.**

---

## 2. Laptop side

Join `leolaser`. Then:

```powershell
set STAND_URL=http://10.42.0.1:8000
py bridge.py --backend com
```

Panel and Grafana in the browser:

| | |
|---|---|
| `http://10.42.0.1:8000/` | control panel |
| `http://10.42.0.1:3000/` | Grafana |

### Three Windows gotchas

**"No Internet" is expected.** There is no upstream. Harmless.

**Windows may silently prefer another adapter.** If the laptop also has cellular, or an
Ethernet cable in a dock, Windows can route to the network that has internet and your POSTs
go nowhere. Disable the other adapters, or accept that this is the first thing to check when
`optical_age_s` climbs.

**Use the IP, not a hostname.** There is no DNS. `laserpi.local` may work through mDNS, but
`10.42.0.1` always works.

---

## 3. Pull the images before you leave

Docker needs internet to fetch images and to build. In the field it has none.

```bash
docker compose pull          # influxdb, grafana
docker compose up -d         # confirm both actually start
```

Once the images are local this works offline forever. The api is not containerised, so
there is nothing to build in the field either.

**Confirm the whole stack runs at home with WiFi switched off**, before you trust it
outdoors.

---

## 4. Fit an RTC battery to the Pi 5

This is the one item that quietly corrupts data.

No internet means no NTP. The Pi 5 has an RTC and a battery connector at **J5**, but no
battery fitted from the factory. Without one, a reboot in the field brings the clock up at
whatever it last saw, so InfluxDB timestamps land at the wrong absolute time and a Grafana
"last 15 minutes" query returns nothing while the data is fine but filed in the past.

Two mitigations, both worth doing:

```bash
# before leaving, with the correct time still available
sudo timedatectl set-ntp false
sudo timedatectl set-time "$(date '+%Y-%m-%d %H:%M:%S')"
timedatectl                      # confirm
```

And fit the battery. A few dollars, and it removes the failure mode permanently.

**Intra-run timing is unaffected either way.** `clock.py` anchors to a monotonic clock, and
the bridge-to-Pi offset is measured by the `/sync/ping` exchange, so relative timing and the
optical alignment stay correct even if absolute time is wrong. Only the absolute labels
suffer. That is a recoverable problem, but only if you notice.

---

## 5. Power

Everything on the board has to be fed.

| Load | Note |
|---|---|
| Pi 5 | Wants 5 V at 5 A. A power bank must support USB-C PD at 27 W |
| LabJack T7 | Its own supply. Not the USB host |
| Chiller | Its own supply |
| Laptop | Its own battery |

Pi 5 undervoltage is a nasty failure because it does not announce itself as a power problem.
It looks like random crashes, USB dropouts, and SD card corruption. If the T7 starts
disconnecting mid-run, suspect power before you suspect the cable.

Check for it:

```bash
vcgencmd get_throttled      # 0x0 is healthy
dmesg | grep -i voltage
```

---

## 6. Pre-departure checklist

| | ☐ |
|---|---|
| `field-ap` tested up and down, indoors | ☐ |
| Laptop joins `leolaser` and reaches `http://10.42.0.1:8000/` | ☐ |
| Docker images pulled, full stack verified with WiFi off | ☐ |
| Pi clock set, RTC battery fitted | ☐ |
| `bridge.py` verified against `10.42.0.1` from the laptop | ☐ |
| `optical_age_s` under 2 s on the panel | ☐ |
| Pi power bank confirmed PD, `get_throttled` returns 0x0 | ☐ |
| T7 opens over USB with the api running | ☐ |
| `.env` has the measured `HASS_ZERO_V` and the verified counter index | ☐ |
| Laptop's other network adapters disabled | ☐ |
