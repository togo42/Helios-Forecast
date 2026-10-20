"""Bounded per-entry reuse of settled weather, independent of the short HTTP cache.

Only elapsed hours are retained. Every refresh still requires real fresh weather;
forecast rows from a previous request never mature into historical observations.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
import re
from typing import Any, Awaitable, Callable

from . import openmeteo
from .openmeteo import WeatherSeries
from .provenance import digest

# Increment on incompatible parser/row semantics, independently of HTTP cache TTL.
HISTORY_SCHEMA = 1
RECENT_PAST_DAYS = 1
BACKFILL_INTERVAL = timedelta(days=1)
_FIELDS = ("cloud", "shortwave", "direct", "diffuse", "temp", "wind", "snow", "cloud_spread")
_MAX_ROWS = 61 * 24  # 60 full UTC days plus the elapsed part of today
_MAX_RECEIPTS = 2 * _MAX_ROWS
_MAX_STORE_BYTES = 2_000_000


def history_identity(lat: float, lon: float) -> str:
    """Bind the actual API coordinates, model choice, variables and parser schema."""
    return digest(
        {
            "schema": HISTORY_SCHEMA,
            "coordinates": [f"{lat:.4f}", f"{lon:.4f}"],
            "models": openmeteo.pick_models_for_location(lat, lon),
            "spread_models": openmeteo.WEATHER_MODELS,
            "variables": [openmeteo.WEATHER_HOURLY, openmeteo.WEATHER_SPREAD_HOURLY],
            "parser": "parse_weather/parse_cloud_spread",
        }
    )


@dataclass
class _Row:
    values: list[float | None]
    receipts: tuple[str, ...]


class WeatherHistory:
    """One installation's rolling UTC-day history, with original row receipts."""

    def __init__(self, *, history_days: int = 60, forecast_days: int = 8) -> None:
        if not 1 <= history_days <= 60 or not 1 <= forecast_days <= 16:
            raise ValueError("Weather window exceeds the bounded provider window")
        self.history_days = history_days
        self.forecast_days = forecast_days
        self._identity: str | None = None
        self._successful = False
        self._rows: dict[datetime, _Row] = {}
        self._receipts: dict[str, dict[str, Any]] = {}
        self._last_backfill: datetime | None = None

    def matches(self, lat: float, lon: float) -> bool:
        return self._successful and self._identity == history_identity(lat, lon)

    def _start(self, now: datetime) -> datetime:
        return now.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(
            days=self.history_days
        )

    def _prune(self, now: datetime) -> None:
        start = self._start(now)
        hour = now.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
        self._rows = {t: r for t, r in self._rows.items() if start <= t < hour}
        used = {key for row in self._rows.values() for key in row.receipts}
        self._receipts = {key: value for key, value in self._receipts.items() if key in used}

    def _needs_backfill(self, now: datetime) -> bool:
        if self._last_backfill is not None and now - self._last_backfill < BACKFILL_INTERVAL:
            return False
        if not self._rows:
            return True
        # Missing variables are legitimate missing evidence, not missing timestamps.
        # A full request can repair missing hours, at most once per day per attempt.
        t = self._start(now)
        settled_end = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=RECENT_PAST_DAYS)
        while t < settled_end:
            if t not in self._rows:
                return True
            t += timedelta(hours=1)
        return False

    def _usable_forecast(self, series: WeatherSeries, now: datetime) -> bool:
        """At least one returned forecast hour has actual radiation and cloud input."""
        hour = now.replace(minute=0, second=0, microsecond=0)
        end = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=self.forecast_days)

        def finite(value: float | None) -> bool:
            return value is not None and not isinstance(value, bool) and math.isfinite(value) and value >= 0

        def at(values: list, i: int) -> float | None:
            return values[i] if i < len(values) else None

        for i, t in enumerate(series.times):
            cloud = at(series.cloud, i)
            radiation = finite(at(series.shortwave, i)) or (
                finite(at(series.direct, i)) and finite(at(series.diffuse, i))
            )
            if t.tzinfo is not None and hour <= t < end and finite(cloud) and radiation:
                return True
        return False

    async def fetch(
        self,
        session: Any,
        lat: float,
        lon: float,
        *,
        now: datetime,
        fetcher: Callable[..., Awaitable[WeatherSeries | None]],
    ) -> WeatherSeries | None:
        """Fetch fresh recent inputs, then assemble copies with compatible settled rows.

        None, exceptions and cancellation never install new rows. A changed identity
        invalidates previous history before requesting weather, including failure fallback.
        """
        now = now.astimezone(timezone.utc)
        identity = history_identity(lat, lon)
        if identity != self._identity:
            self._identity = identity
            self._successful = False
            self._rows = {}
            self._receipts = {}
            self._last_backfill = None
        self._prune(now)
        backfill = self._needs_backfill(now)
        if backfill:
            try:
                fresh = await fetcher(session, lat, lon, past_days=self.history_days, forecast_days=self.forecast_days)
            except Exception:  # cancellation still propagates; no alternate provider or background task
                fresh = None
            # Record attempts separately from usable input. Permanent historical gaps
            # and provider failures must not create a large request every 30 minutes.
            self._last_backfill = now
            if fresh is None or not self._usable_forecast(fresh, now):
                fresh = await fetcher(session, lat, lon, past_days=RECENT_PAST_DAYS, forecast_days=self.forecast_days)
        else:
            fresh = await fetcher(session, lat, lon, past_days=RECENT_PAST_DAYS, forecast_days=self.forecast_days)
        if fresh is None or not self._usable_forecast(fresh, now):
            return None
        if any(len(getattr(fresh, name)) not in (0, len(fresh.times)) for name in _FIELDS):
            raise ValueError("Weather arrays must align with timestamps")
        # Keep the original receipt intact; the separate used_hours binding says which
        # assembled inputs came from it. A latest receipt never relabels old rows.
        receipts = deepcopy(fresh.receipts)
        keys = tuple(digest(receipt) for receipt in receipts)
        receipt_map = dict(zip(keys, receipts))
        rows = dict(self._rows)
        start = self._start(now)
        end = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=self.forecast_days)
        for i, t in enumerate(fresh.times):
            if t.tzinfo is None or t.utcoffset() != timedelta(0) or t != t.replace(minute=0, second=0, microsecond=0):
                raise ValueError("Weather timestamps must be whole UTC hours")
            if start <= t < end:
                # None replaces a previous value too; no forward fill or synthetic zero.
                rows[t] = _Row([getattr(fresh, name)[i] if getattr(fresh, name) else None for name in _FIELDS], keys)
        self._identity = identity
        self._successful = True
        self._receipts.update(receipt_map)
        self._rows = rows
        assembled = self._series(rows, fresh)
        self._prune(now)
        return assembled

    def _series(self, rows: dict[datetime, _Row], fresh: WeatherSeries) -> WeatherSeries:
        times = sorted(rows)
        used: dict[str, list[str]] = {}
        for t in times:
            for key in rows[t].receipts:
                used.setdefault(key, []).append(t.isoformat())
        receipts = [dict(deepcopy(self._receipts[key]), used_hours=hours) for key, hours in sorted(used.items())]
        # Existing WeatherSeries numeric annotations predate provider null handling;
        # its parser already returns nullable numeric arrays. Preserve those values.
        arrays: dict[str, Any] = {name: [rows[t].values[i] for t in times] for i, name in enumerate(_FIELDS)}
        return WeatherSeries(
            times=times, **arrays, received_at=fresh.received_at, retrieval="assembled", receipts=receipts
        )

    def dump(self, now: datetime) -> dict[str, Any]:
        """Small checksummed HA Store payload; forecasts and site configuration excluded."""
        self._prune(now)
        payload = {
            "schema": HISTORY_SCHEMA,
            "identity": self._identity,
            "last_backfill": self._last_backfill.isoformat() if self._last_backfill else None,
            "rows": [[t.isoformat(), row.values, list(row.receipts)] for t, row in sorted(self._rows.items())],
            "receipts": self._receipts,
        }
        return {"payload": deepcopy(payload), "sha256": digest(payload)}

    def restore(self, stored: Any, lat: float, lon: float, *, now: datetime) -> bool:
        """Reject corrupt, incompatible, future-dated or oversized persisted data."""
        import json

        try:
            if len(json.dumps(stored, allow_nan=False)) > _MAX_STORE_BYTES:
                return False
            payload = stored["payload"]
            if stored["sha256"] != digest(payload) or payload["schema"] != HISTORY_SCHEMA:
                return False
            if payload["identity"] != history_identity(lat, lon):
                return False
            rows, receipts = payload["rows"], payload["receipts"]
            if (
                not isinstance(rows, list)
                or len(rows) > _MAX_ROWS
                or not isinstance(receipts, dict)
                or len(receipts) > _MAX_RECEIPTS
            ):
                return False
            future = now.astimezone(timezone.utc) + timedelta(minutes=5)
            for key, receipt in receipts.items():
                if key != digest(receipt) or not re.fullmatch(r"[0-9a-f]{64}", receipt["payload_sha256"]):
                    return False
                received = datetime.fromisoformat(receipt["received_at"])
                if received.tzinfo is None or received > future:
                    return False
            parsed: dict[datetime, _Row] = {}
            for stamp, values, refs in rows:
                t = datetime.fromisoformat(stamp)
                if (
                    t.tzinfo is None
                    or t.utcoffset() != timedelta(0)
                    or t != t.replace(minute=0, second=0, microsecond=0)
                    or t >= now
                ):
                    return False
                if not isinstance(values, list) or len(values) != len(_FIELDS):
                    return False
                if any(v is not None and (type(v) not in (int, float) or not math.isfinite(v)) for v in values):
                    return False
                if (
                    not isinstance(refs, list)
                    or len(refs) > 2
                    or any(key not in receipts for key in refs)
                    or t in parsed
                ):
                    return False
                parsed[t] = _Row(values, tuple(refs))
            last = datetime.fromisoformat(payload["last_backfill"]) if payload["last_backfill"] else None
            if last is not None and (last.tzinfo is None or last > future):
                return False
        except (KeyError, TypeError, ValueError, OverflowError):
            return False
        self._identity = payload["identity"]
        self._successful = True
        self._rows = deepcopy(parsed)
        self._receipts = deepcopy(receipts)
        self._last_backfill = last
        self._prune(now)
        return bool(self._rows)
