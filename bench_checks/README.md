# Bench checks

Three standalone scripts. They do not need the main stack, do not import anything
from it, and change nothing. Copy this folder anywhere and run it.

| Script | Runs on | Answers |
|---|---|---|
| `check_labjack.py` | Pi | is every T7 channel alive, and is 20 Hz achievable |
| `check_ophir.py` | **laptop first**, then Pi | what is the Juno plugged into, and can anything read it |
| `check_network.py` | either | are the Pi, T7, and services reachable |

---

## Install

On the Pi:

```bash
sudo apt install -y python3-pip
pip3 install -r requirements.txt --break-system-packages
```

`check_labjack.py` also needs LabJack's **native LJM library**, which is a separate
download and is architecture-specific. `uname -m` will say `aarch64` on a Pi 5.
Get the Linux ARM64 bundle from
<https://support.labjack.com/docs/ljm-software-installer-downloads-t4-t7-t8-digit>,
then:

```bash
tar xzf labjack_ljm_software_*.tar.gz
cd labjack_ljm_software_*/ && sudo ./labjack_ljm_installer.run
```

**Replug the T7 afterwards.** The installer lays down udev rules, and those only apply
to devices connected after they exist.

On the Windows laptop, for the Ophir side only:

```powershell
py -m pip install pyserial pywin32
```

---

## 1. LabJack

Nothing else may hold the T7. Stop the api first if it is running.

```bash
sudo systemctl stop leolaser-api      # or: docker compose stop api
python3 check_labjack.py
```

USB is the default, so no address is needed. On Ethernet:

```bash
python3 check_labjack.py --conn ETHERNET --id 10.1.0.244
```

### What it checks

| # | Section | What a pass means |
|---|---|---|
| 1 | Identity | device opens, serial, firmware, internal temperature |
| 2 | ADC health | AIN15 ground offset inside ±2 mV **with noise on it** |
| 3 | Analog raw | AIN0-AIN3 raw volts, each against its expected range |
| 4 | Thermistor | AIN-EF 50 accepted, resistance and °C plausible |
| 5 | Digital | FIO0-FIO3 levels, with what each one should read |
| 6 | Counter | DIO-EF index accepted, pulses actually arriving |
| 7 | DAC loopback | opt-in, see below |
| 8 | Benchmark | scan latency, and the max rate it implies |

### Two results people misread

**AIN15 with zero noise is a FAIL, not a clean pass.** A working converter is quiet, not
frozen. A perfectly constant reading is a dead channel. The script checks for that
explicitly.

**FIO1 reading low is CORRECT here.** FIO1 sits on node X, which is DAC0 *through* the
switches. DAC0 is at 0 V during this test, so the chain is unpowered and FIO1 must be low
no matter what the switches are doing. FIO1 high would mean something is feeding the chain
that should not be.

### Section 6 will probably warn, and that is useful

`DIO_EF_COUNTER_INDEX` defaults to 9, which is unverified. If the counter does not move,
it is either the pump being off or the wrong index. Run the pump and try again. If it still
does not move with flow present, the index is wrong.

This matters because a wrong index does not error. It gives you a counter that never
increments, which the stack faithfully reports as a clean, stable, plausible 0.00 LPM.

Try candidates until one counts:

```bash
python3 check_labjack.py --counter-index 8
python3 check_labjack.py --counter-index 9
python3 check_labjack.py --counter-index 10
```

Whichever counts goes in `.env`.

### Section 7 is opt-in for a reason

```bash
python3 check_labjack.py --dac
```

DAC0 **is** the laser enable line. This raises it to 4.5 V. It requires you to type
`LOAD DISCONNECTED` and to jumper DAC0 to AIN1.

The loopback uses AIN1, not AIN3, because your thermistor is on AIN3 now. That also means
you do **not** have to remove the LJTick-Divider module, which the older instructions told
you to do.

It also tests DAC1, which is worth proving given it was previously miswired as an SSR
return and may have been sinking current out of spec.

DAC0 and DAC1 are forced to 0 V on every exit path, including a crash.

---

## 2. Ophir

**Start on the Windows laptop.** That is where the driver exists.

```powershell
# Juno UNPLUGGED
py check_ophir.py --snapshot

# now plug it in, wait 5 seconds
py check_ophir.py
```

The snapshot diff is the point. Ophir hardware often enumerates under a generic USB name,
so name matching alone can miss it. Comparing before and after identifies it by elimination
even when it calls itself nothing useful.

Then the script tries Ophir's COM object, which needs **StarLab installed**. If that
section passes, it opens the device, lists sensor channels, streams for 3 s, and prints
real watts. That is the whole integration proven in one run.

**Close StarLab before running.** It holds the device exclusively.

Also run it on the Pi:

```bash
python3 check_ophir.py
```

If the Juno appears as `/dev/ttyUSB0` or `/dev/ttyACM0` there, that is a good result:
it means you can read it from the Pi with `app/ophir.py` and delete the Windows laptop,
the bridge, and the entire two-clock synchronisation problem from the architecture.

If it shows in `lsusb` but not as a serial port, it needs Ophir's driver and the laptop
stays for now. Their Linux USB package is in beta and worth an email.

---

## 3. Network

From the Pi:

```bash
python3 check_network.py
```

From the laptop:

```powershell
py check_network.py --host 10.1.0.52
```

With the T7 on Ethernet, add it:

```bash
python3 check_network.py --labjack 10.1.0.244
```

It pings, checks each port, hits each service's health endpoint, and prints the api's own
counters: influx reachability, points written, write errors, loop interval, overruns,
source errors.

`influx_reachable: false` right after a first start is normal, InfluxDB takes a moment.
If it persists, `INFLUX_URL` in `.env` is wrong: it must be `http://localhost:8086` when
the api runs on the host, and `http://influxdb:8086` only when it runs in a container.

---

## Suggested order

```
1. laptop:  py check_ophir.py --snapshot      then plug in, run again
2. Pi:      python3 check_ophir.py            is it visible to Linux at all
3. Pi:      sudo systemctl stop leolaser-api
4. Pi:      python3 check_labjack.py          read-only, safe
5. Pi:      python3 check_labjack.py --dac    only with the load disconnected
6. Pi:      sudo systemctl start leolaser-api
7. either:  python3 check_network.py
```

Steps 1 to 4 touch nothing and cannot damage anything. Step 5 asserts the enable line, so
it is the only one that needs the load disconnected and your attention.
