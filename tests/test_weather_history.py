"""Bounded weather reuse, provider revisions and original input custody."""

import asyncio
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from custom_components.helios_forecast import openmeteo
from custom_components.helios_forecast.openmeteo import WeatherSeries
from custom_components.helios_forecast.provenance import digest
from custom_components.helios_forecast.weather_history import WeatherHistory

NOW = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)


def weather(now=NOW, *, past_days=60, value=10.0, receipt="a"):
    start = now.replace(hour=0) - timedelta(days=past_days)
    times = [start + timedelta(hours=i) for i in range((past_days + 8) * 24)]
    n = len(times)
    return WeatherSeries(
        times,
        *[[value] * n for _ in range(7)],
        cloud_spread=[None] * n,
        received_at=now,
        retrieval="network",
        receipts=[{"received_at": now.isoformat(), "payload_sha256": receipt * 64, "issue_time": None}],
    )


def test_initial_backfill_then_short_refresh_replaces_overlap_and_none():
    async def run():
        history = WeatherHistory()
        old = weather()
        revised = weather(past_days=1, value=20, receipt="b")
        revised.temp[0] = None
        fetch = AsyncMock(side_effect=[old, revised])
        first = await history.fetch(None, 50, 8, now=NOW, fetcher=fetch)
        second = await history.fetch(None, 50, 8, now=NOW, fetcher=fetch)
        assert [c.kwargs["past_days"] for c in fetch.call_args_list] == [60, 1]
        assert all(c.kwargs["forecast_days"] == 8 for c in fetch.call_args_list)
        assert len(second.times) == 68 * 24
        assert second.temp[second.times.index(revised.times[0])] is None
        assert second.temp[0] == 10
        assert second.temp[-1] == 20
        assert first.temp[-1] == 10  # no output aliasing
        first.temp[0] = 999
        first.receipts[0]["used_hours"].clear()
        assert second.temp[0] == 10
        assert all(r["used_hours"] for r in second.receipts)
        assert {r["payload_sha256"] for r in second.receipts} == {"a" * 64, "b" * 64}
        old_receipt = next(r for r in second.receipts if r["payload_sha256"] == "a" * 64)
        assert old_receipt["received_at"] == NOW.isoformat()
        assert old_receipt["used_hours"][-1] < revised.times[0].isoformat()
        assert second.retrieval == "assembled"

    asyncio.run(run())


def test_gaps_repair_bounded_daily_and_missing_variables_do_not_trigger_backfill():
    async def run():
        history = WeatherHistory()
        full = weather()
        full.temp[0] = None  # missing variable, not missing hour
        full = replace(
            full,
            times=full.times[1:],
            **{
                name: getattr(full, name)[1:]
                for name in ("cloud", "shortwave", "direct", "diffuse", "temp", "wind", "snow", "cloud_spread")
            },
        )
        fetch = AsyncMock(side_effect=[full, weather(past_days=1), weather(NOW + timedelta(days=1))])
        await history.fetch(None, 50, 8, now=NOW, fetcher=fetch)
        await history.fetch(None, 50, 8, now=NOW + timedelta(minutes=30), fetcher=fetch)
        # New UTC day rolls past this particular hole; remove a retained settled hour instead.
        history._rows.pop(NOW - timedelta(days=10))
        await history.fetch(None, 50, 8, now=NOW + timedelta(days=1), fetcher=fetch)
        assert [c.kwargs["past_days"] for c in fetch.call_args_list] == [60, 1, 60]
        fetch = AsyncMock(return_value=weather(NOW + timedelta(days=2), past_days=1))
        await history.fetch(None, 50, 8, now=NOW + timedelta(days=2), fetcher=fetch)
        assert fetch.call_args.kwargs["past_days"] == 1

    asyncio.run(run())


def test_failed_and_cancelled_fetch_do_not_install_rows_or_receipts():
    async def run():
        history = WeatherHistory()
        await history.fetch(None, 50, 8, now=NOW, fetcher=AsyncMock(return_value=weather()))
        original = history.dump(NOW)
        assert await history.fetch(None, 50, 8, now=NOW, fetcher=AsyncMock(return_value=None)) is None
        for error in (RuntimeError("offline"), asyncio.CancelledError()):
            with pytest.raises(type(error)):
                await history.fetch(None, 50, 8, now=NOW, fetcher=AsyncMock(side_effect=error))
            assert history.dump(NOW) == original
        # Incompatible fallback is forbidden even if the new site's request fails.
        assert await history.fetch(None, 51, 8, now=NOW, fetcher=AsyncMock(return_value=None)) is None
        assert not history.matches(50, 8)
        assert history.dump(NOW)["payload"]["rows"] == []

    asyncio.run(run())


def test_location_models_parser_identity_invalidate(monkeypatch):
    async def run():
        history = WeatherHistory()
        fetch = AsyncMock(return_value=weather())
        await history.fetch(None, 50, 8, now=NOW, fetcher=fetch)
        monkeypatch.setattr(openmeteo, "WEATHER_MODELS", ("other_model",))
        await history.fetch(None, 50, 8, now=NOW, fetcher=fetch)
        monkeypatch.setattr(openmeteo, "WEATHER_HOURLY", "new_parser_variables")
        await history.fetch(None, 50, 8, now=NOW, fetcher=fetch)
        await history.fetch(None, 51, 8, now=NOW, fetcher=fetch)
        assert [c.kwargs["past_days"] for c in fetch.call_args_list] == [60] * 4

    asyncio.run(run())


def test_restart_restores_settled_rows_but_requires_fresh_weather():
    async def run():
        history = WeatherHistory()
        await history.fetch(None, 50, 8, now=NOW, fetcher=AsyncMock(return_value=weather()))
        stored = history.dump(NOW)
        assert len(stored["payload"]["rows"]) <= 61 * 24
        assert all(datetime.fromisoformat(row[0]) < NOW for row in stored["payload"]["rows"])
        restored = WeatherHistory()
        assert restored.restore(stored, 50, 8, now=NOW)
        assert await restored.fetch(None, 50, 8, now=NOW, fetcher=AsyncMock(return_value=None)) is None
        fetch = AsyncMock(return_value=weather(past_days=1, receipt="b"))
        result = await restored.fetch(None, 50, 8, now=NOW, fetcher=fetch)
        assert fetch.call_args.kwargs["past_days"] == 1
        assert {r["payload_sha256"] for r in result.receipts} == {"a" * 64, "b" * 64}
        assert not WeatherHistory().restore(stored, 50, 9, now=NOW)
        assert not WeatherHistory().restore(stored, 50, 8, now=NOW - timedelta(days=1))
        # Valid checksum cannot make a future-dated receipt or oversized rows acceptable.
        for mutate in (
            lambda p: p.update(schema=999),
            lambda p: p.update(rows=p["rows"] * 4),
            lambda p: p["rows"][0][1].__setitem__(0, "bad"),
            lambda p: p["rows"][0].__setitem__(0, (NOW + timedelta(days=1)).isoformat()),
        ):
            broken = deepcopy(stored)
            mutate(broken["payload"])
            broken["sha256"] = digest(broken["payload"])
            assert not WeatherHistory().restore(broken, 50, 8, now=NOW)
        stored["sha256"] = "bad"
        assert not WeatherHistory().restore(stored, 50, 8, now=NOW)

    asyncio.run(run())


def test_old_forecast_hours_never_mature_to_observations_and_long_outage_repairs():
    async def run():
        history = WeatherHistory()
        fetch = AsyncMock(side_effect=[weather(), weather(NOW + timedelta(days=3), receipt="b")])
        await history.fetch(None, 50, 8, now=NOW, fetcher=fetch)
        assert max(history._rows) < NOW
        await history.fetch(None, 50, 8, now=NOW + timedelta(days=3), fetcher=fetch)
        assert [c.kwargs["past_days"] for c in fetch.call_args_list] == [60, 60]
        assert min(history._rows) == (NOW + timedelta(days=3)).replace(hour=0) - timedelta(days=60)

    asyncio.run(run())


def test_failed_large_backfill_uses_real_short_inputs_and_bounds_repair_attempts():
    async def run():
        history = WeatherHistory()
        short = weather(past_days=1, receipt="b")
        fetch = AsyncMock(side_effect=[None, short, short])
        first = await history.fetch(None, 50, 8, now=NOW, fetcher=fetch)
        assert len(first.times) == 9 * 24
        assert min(first.times) == short.times[0]
        assert {r["payload_sha256"] for r in first.receipts} == {"b" * 64}
        await history.fetch(None, 50, 8, now=NOW + timedelta(minutes=30), fetcher=fetch)
        assert [c.kwargs["past_days"] for c in fetch.call_args_list] == [60, 1, 1]
        revived = WeatherHistory()
        assert revived.restore(history.dump(NOW), 50, 8, now=NOW)
        retry = AsyncMock(return_value=short)
        await revived.fetch(None, 50, 8, now=NOW, fetcher=retry)
        assert retry.call_args.kwargs["past_days"] == 1

    asyncio.run(run())


def test_cancelled_initial_backfill_does_not_launch_short_fallback():
    async def run():
        fetch = AsyncMock(side_effect=asyncio.CancelledError())
        history = WeatherHistory()
        with pytest.raises(asyncio.CancelledError):
            await history.fetch(None, 50, 8, now=NOW, fetcher=fetch)
        fetch.assert_awaited_once()
        assert history._last_backfill is None
        assert not history._rows

    asyncio.run(run())


def test_all_missing_forecast_is_not_usable_and_empty_failures_are_rate_limited():
    async def run():
        history = WeatherHistory()
        missing = weather()
        missing.shortwave[:] = [None] * len(missing.times)
        missing.direct[:] = [None] * len(missing.times)
        missing.diffuse[:] = [None] * len(missing.times)
        fetch = AsyncMock(return_value=missing)
        assert await history.fetch(None, 50, 8, now=NOW, fetcher=fetch) is None
        assert not history.matches(50, 8)
        assert not history._rows
        assert await history.fetch(None, 50, 8, now=NOW + timedelta(minutes=30), fetcher=fetch) is None
        assert [c.kwargs["past_days"] for c in fetch.call_args_list] == [60, 1, 1]

    asyncio.run(run())


def test_persisted_future_receipt_with_valid_checksums_is_rejected():
    async def run():
        history = WeatherHistory()
        await history.fetch(None, 50, 8, now=NOW, fetcher=AsyncMock(return_value=weather()))
        stored = history.dump(NOW)
        payload = stored["payload"]
        old_key, receipt = next(iter(payload["receipts"].items()))
        receipt["received_at"] = (NOW + timedelta(days=1)).isoformat()
        new_key = digest(receipt)
        payload["receipts"] = {new_key: receipt}
        for row in payload["rows"]:
            row[2] = [new_key if key == old_key else key for key in row[2]]
        stored["sha256"] = digest(payload)
        assert not WeatherHistory().restore(stored, 50, 8, now=NOW)
        stored = history.dump(NOW)
        stored["padding"] = "x" * 2_000_001
        assert not WeatherHistory().restore(stored, 50, 8, now=NOW)

    asyncio.run(run())


def test_real_split_radiation_remains_usable_without_ghi():
    async def run():
        history = WeatherHistory()
        split = weather()
        split.shortwave[:] = [None] * len(split.times)
        result = await history.fetch(None, 50, 8, now=NOW, fetcher=AsyncMock(return_value=split))
        assert result is not None
        assert result.shortwave == [None] * len(split.times)
        assert result.direct == split.direct
        assert result.diffuse == split.diffuse
        assert history.matches(50, 8)

    asyncio.run(run())
