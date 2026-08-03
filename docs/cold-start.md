# Cold Start — Everything Unplugged to Verified Stand

Follow in order. Nothing here energises the array or the laser.

---

# PART 0 · Gather

## Downloads

| What | Where | Onto |
|---|---|---|
| `leolaser.zip` | this conversation | laptop, then Pi |
| `bench_checks.zip` | this conversation | laptop, then Pi |
| **LabJack LJM, Linux ARM64** | support.labjack.com → LJM software installer downloads | Pi |
| **Ophir StarLab** | ophiropt.com → downloads | Windows laptop |

LJM and StarLab are manual downloads. LJM is architecture-specific and StarLab is the only
thing that can talk to the Juno, so neither can be scripted.

## Parts

| Qty | Part | For |
|---|---|---|
| 1 | 10 kΩ, 1%, metal film | HASS load resistor. 1% matters, it sets the sensitivity |
| 1 | 3.3 kΩ, 5% | FIO0 pull-up |
| 1 | 6.8 kΩ, 5% | FIO0 to GND |
| 1 | short jumper wire | DAC0 → AIN1 loopback during self-test |
| — | ferrules or heatshrink | T7 terminals will take 3 conductors, badly |

## Confirm before wiring

`uname -m` on the Pi. `aarch64` means you want the ARM64 LJM bundle, not x86_64.

---

# PART 1 · Bench wiring, nothing powered

Array disconnected and covered. Laser not connected. SSR load side disconnected.

## 1.1 Resolve the analog channel conflict first

**The LJTick-Divider-25 is a two-channel module.** Fitted to the AIN2/AIN3 block it drives
*both* AIN2 and AIN3, which means AIN3 is not available. A discrete two-resistor divider on
AIN2 does leave AIN3 free.

Settle it in thirty seconds:

```
Is a module physically plugged onto the AIN2/AIN3 terminal block?
   YES → AIN3 is occupied. Thermistor goes on AIN1.  THERMISTOR_AIN=1
   NO  → discrete divider. AIN3 is free.             THERMISTOR_AIN=3
```

Write the answer down. It goes in `.env` and everything downstream depends on it.

## 1.2 HASS 50-S

Identify pin 1 from the **moulded key on the Molex housing**, not by counting from an end.
Counting is what produced the current miswire.

| Pin | Signal | Wire to |
|---|---|---|
| 1 | Uref | **nothing. Leave floating** |
| 2 | Output | AIN0 |
| 3 | 0 V | GND, same block as AIN0 |
| 4 | +5 V | VS |

Plus **10 kΩ from pin 2 to pin 3**, soldered at the connector end, heatshrunk. The datasheet's
12.5 mV/A is specified into a 10 kΩ load; without it your sensitivity is not the number on
the label.

Do not ground pin 1. Open and grounded are not the same thing — grounding it fights the
internal reference buffer just as hard as the 5 V did.

## 1.3 Thermistor

Two-wire NTC, no polarity. Onto whichever channel 1.1 gave you.

```
   leg 1 ──┬──▶ 200UA terminal
           └──▶ AIN1 or AIN3        (two wires share the 200UA terminal)
   leg 2 ─────▶ GND
```

## 1.4 Voltage sense

Leave as is. Output lands on AIN2 either way.

## 1.5 Flow sensor, Koolance INS-FM17N

Two wires, no polarity.

```
  VS ──[ 3.3 kΩ ]──┬──▶ FIO0 ──── reed wire A
                   │
                [ 6.8 kΩ ]
                   │
                  GND ──── reed wire B
```

Both resistors and reed wire A meet at FIO0. Use the GND **in the FIO0/FIO1 block**, not one
across the board. Three conductors in one screw terminal is the awkward part — twist them or
pigtail them.

Gives 1.5 mA of contact wetting current and a 3.37 V logic high. Do not use the T7's internal
pull-up: at ~100 kΩ it delivers 33 µA, which does not break through contact oxide, and missed
closures read as clean, stable, plausible low flow.

## 1.6 Interlock chain

You confirmed this is already correct. Verify visually, do not rewire.

```
DAC0 ─▶ E-stop ─▶ rotary key ─▶ lid switch ─▶ coolant switch ─▶ node X ─▶ SSR control (+)
                                                                  │
                                                     10k/20k ─────▶ FIO1
                                              SSR control (−) ─────▶ GND, adjacent terminal
```

DAC1 unused.

## 1.7 Connect the T7 to the Pi

**USB.** T7's own power supply plugged in separately — do not power it from the USB host.

## 1.8 Network, bench phase

Pi Ethernet into your LAN switch. Laptop on the same LAN. Field AP mode comes later.

---

# PART 2 · Pi software

## 2.1 Power up and find it

```powershell
ping -n 2 laserpi.local
```

If that fails, check your router's client list. Then:

```powershell
ssh laser@<pi-ip>
```

## 2.2 Docker

```bash
docker --version
```

If it errors:

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
```

**Log out and back in.** The group change does not apply to your current session, and the
error you get otherwise is a confusing permissions message.

## 2.3 Copy the files over

From the laptop:

```powershell
scp $HOME\Downloads\leolaser.zip laser@<pi-ip>:~/
scp $HOME\Downloads\bench_checks.zip laser@<pi-ip>:~/
scp $HOME\Downloads\labjack_ljm_software_*.tar.gz laser@<pi-ip>:~/
```

On the Pi:

```bash
sudo apt update && sudo apt install -y unzip python3-venv python3-pip
unzip -o leolaser.zip
unzip -o bench_checks.zip
```

## 2.4 Install LJM

```bash
tar xzf labjack_ljm_software_*.tar.gz
cd labjack_ljm_software_*/
sudo ./labjack_ljm_installer.run
cd ~
```

**Unplug and replug the T7 now.** The installer writes udev rules and they only apply to
devices connected afterwards.

```bash
lsusb | grep -i labjack
```

That must return a line. If it does not, the OS cannot see the T7 and nothing below will work.

## 2.5 Set up the stack

```bash
cd ~/leolaser
./install/setup_pi.sh
```

Creates `.venv`, installs dependencies, copies `.env.example` to `.env`, checks that LJM
imports, installs the systemd unit. **If it stops at the LJM check, 2.4 did not complete.**

## 2.6 Edit .env

```bash
nano .env
```

Three lines now, four more after verification.

```
SOURCE=sim
THERMISTOR_AIN=3          # or 1, per step 1.1
LABJACK_CONN=USB
```

Ctrl-O to save, Ctrl-X to exit. Leave `SOURCE=sim` — you are not ready for real hardware yet.

## 2.7 Start it

```bash
docker compose pull
docker compose up -d
sudo systemctl start leolaser-api
```

`docker compose pull` before `up` so the images are cached locally. That is what makes the
field work offline later.

---

# PART 3 · Verify with no hardware in the loop

```bash
curl -s localhost:8000/health
python3 ~/bench_checks/check_network.py
```

`influx_reachable` must be `true`. If false, wait 20 s and retry — InfluxDB takes a moment on
first run.

Then from the laptop's browser: `http://<pi-ip>:8000/`

| Check | Expect |
|---|---|
| Top right | `LINK UP` |
| Press Arm | chip turns amber, `ARMED` |
| Press Enable | `run_id` appears, current ramps to ~10.2 A |
| Press Stop, then Reset | back to `IDLE` |

Also open `http://<pi-ip>:3000/` and confirm the Direct-drive dashboard has data.

**That is the entire software stack proven.** Everything remaining is hardware.

---

# PART 4 · Verify the LabJack

The api and the tools cannot both hold the device.

```bash
sudo systemctl stop leolaser-api
cd ~/bench_checks
pip3 install -r requirements.txt --break-system-packages
python3 check_labjack.py
```

Work through the sections. Three results that look wrong and are not:

**AIN15 with zero noise is a FAIL.** A live converter is quiet, not frozen. A perfectly
constant value is a dead channel.

**FIO1 low is correct.** It reads node X, which is DAC0 downstream of the switches. DAC0 is at
0 V, so the chain is unpowered and FIO1 must read low regardless of switch positions.

**The counter section will probably warn.** `DIO_EF_COUNTER_INDEX` is unverified. Run the
pump, then:

```bash
python3 check_labjack.py --counter-index 8
python3 check_labjack.py --counter-index 9
python3 check_labjack.py --counter-index 10
```

Whichever actually counts goes in `.env`. A wrong index does not error — it gives a counter
that never increments, reported as a clean, stable 0.00 LPM.

## 4.1 The HASS verdict

| Step | Expect | Meaning if it fails |
|---|---|---|
| DMM, pin 1 to pin 3 | **~2.5 V** | Reference buffer did not survive the 5 V. Sensor is scrap |
| AIN0 in section 3 | **~2.5 V with noise** | Static means dead channel |
| 10 turns at 1.2 A | **12.0 A ±1%** | Reference alive but Hall front end damaged. Replace |
| Reverse the conductor | sign flips | HASS conductor runs backwards through the window. Fix the wire, not the software |

**Order a replacement the same day if any of these fail.** It is your last week and there is
no lead time to spare.

## 4.2 DAC test

Load side disconnected. Jumper DAC0 to **AIN1**.

```bash
python3 check_labjack.py --dac
```

Type `LOAD DISCONNECTED` when prompted. Both DACs are forced to 0 V on every exit path.

The loopback uses AIN1, not AIN3, so you do **not** need to remove the LJTick module.

## 4.3 Interlock chain, one switch at a time

DAC0 at 5 V, DMM on SSR control (+), load disconnected:

| Action | SSR control + |
|---|---|
| All switches closed | ~5 V |
| Open E-stop only | **0 V** |
| Open rotary key only | **0 V** |
| Open lid only | **0 V** |
| Open coolant switch only | **0 V** |

Four separate tests. If any one fails to break the loop on its own, stop and rewire — the
entire safety argument rests on this property.

## 4.4 Record the numbers

```bash
python3 check_labjack.py --zero-hass 2>/dev/null || true
```

Or from the earlier run. Then:

```bash
cd ~/leolaser && nano .env
```

```
HASS_ZERO_V=<measured>
DIO_EF_COUNTER_INDEX=<whichever counted>
THERMISTOR_AIN=<1 or 3>
SOURCE=labjack
```

```bash
sudo systemctl start leolaser-api
curl -s localhost:8000/health
```

Panel should now show real numbers: ~0.00 A, ~0.0 V, ambient temperature, live flow.

---

# PART 5 · Ophir

## 5.1 On the Windows laptop

Install StarLab first. Then, **Juno still unplugged**:

```powershell
cd Downloads\bench_checks
py -m pip install -r requirements.txt
py check_ophir.py --snapshot
```

Now plug the Juno into a laptop USB port. Wait 5 seconds.

```powershell
py check_ophir.py
```

The diff names the device even if it enumerates under a generic USB name. Then the script
tries the COM object: opens it, lists sensor channels, streams for 3 s, prints real watts.

**Close StarLab before running.** It holds the device exclusively.

## 5.2 Connect the sensor

FL400A-BB-50 into the Juno. Sensor fan needs airflow. Re-run `check_ophir.py` — the sensor
channel should now appear by name.

## 5.3 Start the bridge

```powershell
cd Downloads\leolaser\bridge
py -m pip install -r requirements.txt
set STAND_URL=http://<pi-ip>:8000
py bridge.py --backend com
```

On the panel, the Optical tile should populate and `optical_age_s` should sit under 2 s.

## 5.4 Also check it from the Pi

```bash
python3 ~/bench_checks/check_ophir.py
```

If the Juno appears as `/dev/ttyACM0` there, that is a good outcome: you can read it from the
Pi with `app/ophir.py` and remove the laptop, the bridge, and the two-clock sync problem from
the architecture entirely. Worth five minutes to find out.

---

# PART 6 · Going to the field

Only after Parts 1 to 5 pass. See `FIELD_CONFIG.md` for the detail. Summary:

```bash
# once, indoors
sudo nmcli con add type wifi ifname wlan0 con-name field-ap autoconnect no ssid leolaser
sudo nmcli con modify field-ap 802-11-wireless.mode ap 802-11-wireless.band bg ipv4.method shared
sudo nmcli con modify field-ap wifi-sec.key-mgmt wpa-psk wifi-sec.psk "<password>"

# time source, since there is no NTP out there
sudo apt install -y chrony
echo "allow 10.42.0.0/24" | sudo tee -a /etc/chrony/chrony.conf
echo "local stratum 10"   | sudo tee -a /etc/chrony/chrony.conf
sudo systemctl restart chrony
```

Field: `sudo nmcli con up field-ap`. Pi is at **10.42.0.1**. Laptop joins `leolaser`,
`STAND_URL=http://10.42.0.1:8000`.

Fit an RTC battery to the Pi 5 at J5. Without it a reboot in the field brings the clock up
wrong, your data lands at the wrong absolute time, and Grafana shows an empty dashboard over
perfectly good data.

---

# Reference · Final channel map

| Terminal | Signal | Notes |
|---|---|---|
| AIN0 | HASS Output, pin 2 | ±10 V range. 10 kΩ load at the connector |
| AIN1 | free, or thermistor | per step 1.1. Also the DAC loopback point |
| AIN2 | voltage divider output | ×25 |
| AIN3 | thermistor, or driven by LJTick ch B | per step 1.1 |
| FIO0 | flow reed | 3.3k/6.8k divider from VS |
| FIO1 | node X readback | 10k/20k divider |
| FIO2 | free | 1-Wire bus later |
| FIO3 | free | comparator trip latch later |
| DAC0 | SSR gate, through the chain | 5.0 V = enabled |
| DAC1 | unused | |
| 200UA | thermistor excitation | bridged to the thermistor channel |
| VS | 5 V | HASS, FIO0 divider |
| GND | common | single-point tie to node N |

---

# Troubleshooting

| Symptom | Cause |
|---|---|
| `lsusb` shows no LabJack | LJM not installed, or T7 not replugged after installing |
| Tool says device busy | api still running. `sudo systemctl stop leolaser-api` |
| `influx_reachable: false` | wait 20 s on first start. Then check `INFLUX_URL` is `http://localhost:8086` |
| Panel shows `LINK DOWN` | api not running, or wrong IP in the browser |
| Flow reads exactly 0.00 always | wrong `DIO_EF_COUNTER_INDEX`, or the divider is not wired |
| Current reads negative | HASS conductor reversed through the window |
| Current sticks near 5 V raw | Uref still on a rail |
| Temperature implausible | wrong `THERMISTOR_AIN`, or placeholder Steinhart-Hart coefficients |
| Random Pi crashes, USB dropouts | Pi 5 undervoltage. `vcgencmd get_throttled` should be `0x0` |
| Grafana UI hangs on load | offline without the analytics flags. Pull the latest `docker-compose.yml` |
| Grafana empty but data exists | Pi and laptop clocks disagree. Set up chrony per Part 6 |
