"""Optional DS18B20 temperature bus on FIO2. No-ops when disabled."""

import asyncio
import os
import time

ENABLED = os.getenv("ONEWIRE_ENABLED", "0") == "1"
DQ_DIONUM = int(os.getenv("ONEWIRE_DQ_DIONUM", "2"))
POLL_INTERVAL_S = float(os.getenv("ONEWIRE_POLL_S", "2.0"))
STALE_AFTER_S = float(os.getenv("ONEWIRE_STALE_S", "8.0"))

FUNC_SEARCH = 0xF0
FUNC_MATCH = 0x55
FUNC_SKIP = 0xCC

CMD_CONVERT = 0x44
CMD_READ_SCRATCHPAD = 0xBE

CONVERSION_S = 0.80


def _roles() -> dict[str, int]:
    """ONEWIRE_ROLES="t_module:28FF01A2...,t_coolant_in:28FF02B3..." (hex ROMs)."""
    raw = os.getenv("ONEWIRE_ROLES", "").strip()
    out: dict[str, int] = {}
    for entry in raw.split(","):
        if ":" not in entry:
            continue
        name, rom = entry.split(":", 1)
        name, rom = name.strip(), rom.strip()
        if name and rom:
            out[name] = int(rom, 16)
    return out


class OneWireBus:
    def __init__(self, source):
        self.roles = _roles()
        self.values: dict[str, float] = {}
        self.updated_at: dict[str, float] = {}
        self.errors = 0
        self.enabled = ENABLED and bool(self.roles) and hasattr(source, "handle")
        self._ljm = getattr(source, "_ljm", None)
        self._handle = getattr(source, "handle", None)
        if self.enabled:
            self._configure()

    def _configure(self):
        self._ljm.eWriteNames(
            self._handle, 3,
            ["ONEWIRE_DQ_DIONUM", "ONEWIRE_DPU_DIONUM", "ONEWIRE_OPTIONS"],
            [DQ_DIONUM, 0, 0],
        )

    def _txn(self, function: int, rom: int | None, tx: list[int], rx_bytes: int):
        names = ["ONEWIRE_FUNCTION", "ONEWIRE_NUM_BYTES_TX", "ONEWIRE_NUM_BYTES_RX"]
        values = [function, len(tx), rx_bytes]
        if rom is not None:
            names += ["ONEWIRE_ROM_MATCH_H", "ONEWIRE_ROM_MATCH_L"]
            values += [(rom >> 32) & 0xFFFFFFFF, rom & 0xFFFFFFFF]
        self._ljm.eWriteNames(self._handle, len(names), names, values)
        if tx:
            self._ljm.eWriteNameByteArray(self._handle, "ONEWIRE_DATA_TX", len(tx), tx)
        self._ljm.eWriteName(self._handle, "ONEWIRE_GO", 1)
        if rx_bytes:
            return self._ljm.eReadNameByteArray(
                self._handle, "ONEWIRE_DATA_RX", rx_bytes)
        return []

    def search(self) -> list[int]:
        """Enumerate ROM addresses. Run once from a tool to populate ONEWIRE_ROLES."""
        if not self.enabled and self._handle is None:
            return []
        found = []
        self._txn(FUNC_SEARCH, None, [], 0)
        hi, lo = self._ljm.eReadNames(
            self._handle, 2,
            ["ONEWIRE_SEARCH_RESULT_H", "ONEWIRE_SEARCH_RESULT_L"])
        rom = (int(hi) << 32) | int(lo)
        if rom:
            found.append(rom)
        return found

    def poll_once(self):
        if not self.enabled:
            return
        try:
            self._txn(FUNC_SKIP, None, [CMD_CONVERT], 0)
        except Exception:
            self.errors += 1
            return

        time.sleep(CONVERSION_S)

        for name, rom in self.roles.items():
            try:
                data = self._txn(FUNC_MATCH, rom, [CMD_READ_SCRATCHPAD], 9)
                raw = (data[1] << 8) | data[0]
                if raw & 0x8000:
                    raw -= 1 << 16
                self.values[name] = round(raw / 16.0, 3)
                self.updated_at[name] = time.monotonic()
            except Exception:
                self.errors += 1

    async def run(self):
        if not self.enabled:
            return
        while True:
            await asyncio.to_thread(self.poll_once)
            await asyncio.sleep(POLL_INTERVAL_S)

    def snapshot(self) -> dict:
        """Values plus per-channel age, so a dead probe reads stale not frozen."""
        if not self.enabled:
            return {}
        now = time.monotonic()
        out = {}
        for name in self.roles:
            age = now - self.updated_at.get(name, -1e9)
            if name in self.values and age <= STALE_AFTER_S:
                out[name] = self.values[name]
                out[f"{name}_age_s"] = round(age, 2)
            else:
                out[f"{name}_stale"] = 1
        if "t_coolant_in" in out and "t_coolant_out" in out:
            out["coolant_dt_c"] = round(out["t_coolant_out"] - out["t_coolant_in"], 3)
        return out
