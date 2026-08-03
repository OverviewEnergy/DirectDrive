"""InfluxDB v2 batched write client."""

import asyncio
import time

import httpx


def _esc_tag(value: str) -> str:
    """Line protocol: commas, equals signs, and spaces must be escaped in tags."""
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace(",", "\\,")
        .replace("=", "\\=")
        .replace(" ", "\\ ")
    )


def _esc_measurement(value: str) -> str:
    """Measurement names escape commas and spaces (but not equals)."""
    return str(value).replace("\\", "\\\\").replace(",", "\\,").replace(" ", "\\ ")


def _fmt_field(value) -> str:
    """Field values are TYPED in line protocol, and the type is in the syntax:"""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return f"{value}i"
    if isinstance(value, float):
        return repr(value)
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


class InfluxWriteError(Exception):
    """Raised on a failed flush. Callers may log it and carry on."""


class InfluxClient:
    """Batching writer for InfluxDB v2"""

    def __init__(
        self,
        url: str,
        token: str,
        org: str,
        bucket: str,
        batch_size: int = 50,
        flush_interval_s: float = 1.0,
        timeout_s: float = 5.0,
    ):
        self.url = url.rstrip("/")
        self.token = token
        self.org = org
        self.bucket = bucket
        self.batch_size = batch_size
        self.flush_interval_s = flush_interval_s
        self.timeout_s = timeout_s

        self._client: httpx.AsyncClient | None = None
        self._buffer: list[str] = []
        self._last_flush = time.monotonic()
        self._lock = asyncio.Lock()  # keeps two flushes from racing on the buffer

        self.points_written = 0
        self.write_errors = 0

    async def open(self):
        """Create the pooled HTTP connection. One client, reused for every write."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout_s)

    async def close(self):
        """Flush whatever is buffered, then release the connection."""
        try:
            await self.flush()
        finally:
            if self._client is not None:
                await self._client.aclose()
                self._client = None

    async def __aenter__(self):
        await self.open()
        return self

    async def __aexit__(self, *exc):
        await self.close()

    def line_protocol(
        self, measurement: str, tags: dict, fields: dict, timestamp_ns: int | None = None
    ) -> str:
        """Build one line protocol record:"""
        if not fields:
            raise ValueError("a point needs at least one field")

        parts = [_esc_measurement(measurement)]
        for k, v in tags.items():
            if v is None or v == "":
                continue
            parts.append(f"{_esc_tag(k)}={_esc_tag(v)}")
        key = ",".join(parts)

        field_str = ",".join(f"{_esc_tag(k)}={_fmt_field(v)}" for k, v in fields.items())
        ts = time.time_ns() if timestamp_ns is None else timestamp_ns
        return f"{key} {field_str} {ts}"

    def write(
        self, measurement: str, tags: dict, fields: dict, timestamp_ns: int | None = None
    ):
        """Queue one point. Cheap and synchronous -- no network here."""
        self._buffer.append(self.line_protocol(measurement, tags, fields, timestamp_ns))

    @property
    def pending(self) -> int:
        return len(self._buffer)

    def _due(self) -> bool:
        if not self._buffer:
            return False
        if len(self._buffer) >= self.batch_size:
            return True
        return (time.monotonic() - self._last_flush) >= self.flush_interval_s

    async def flush_if_due(self) -> int:
        """Flush only if the batch is full or the interval elapsed. Call this each loop."""
        return await self.flush() if self._due() else 0

    async def flush(self) -> int:
        """POST the buffered points. Returns how many were sent"""
        async with self._lock:
            if not self._buffer:
                return 0
            if self._client is None:
                await self.open()

            batch, self._buffer = self._buffer, []
            body = "\n".join(batch)

            try:
                resp = await self._client.post(
                    f"{self.url}/api/v2/write",
                    params={"org": self.org, "bucket": self.bucket, "precision": "ns"},
                    headers={
                        "Authorization": f"Token {self.token}",
                        "Content-Type": "text/plain; charset=utf-8",
                    },
                    content=body,
                )
                resp.raise_for_status()
            except Exception as e:
                self.write_errors += 1
                # Re-queue and cap the backlog.
                self._buffer = (batch + self._buffer)[-10 * self.batch_size :]
                raise InfluxWriteError(f"write failed ({len(batch)} points): {e}") from e

            self._last_flush = time.monotonic()
            self.points_written += len(batch)
            return len(batch)

    async def ping(self) -> bool:
        """True if InfluxDB is reachable and healthy. Good for a startup check."""
        if self._client is None:
            await self.open()
        try:
            resp = await self._client.get(f"{self.url}/health")
            return resp.status_code == 200
        except Exception:
            return False

    def stats(self) -> dict:
        return {
            "points_written": self.points_written,
            "write_errors": self.write_errors,
            "pending": self.pending,
        }
