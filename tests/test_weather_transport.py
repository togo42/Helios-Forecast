"""Concurrency and ownership expectations, without real weather traffic."""

import asyncio

import pytest

from custom_components.helios_forecast import weather_transport as mod


def test_shares_and_copies_and_expires(monkeypatch):
    async def run():
        cache = mod.WeatherTransport()
        session, parser = object(), object()
        calls = 0

        async def fetch():
            nonlocal calls
            calls += 1
            await asyncio.sleep(0)
            return [1]

        a, b = await asyncio.gather(cache.fetch(session, "u", parser, fetch), cache.fetch(session, "u", parser, fetch))
        assert calls == 1
        a.append(2)
        assert b == [1]
        assert await cache.fetch(session, "u", parser, fetch) == [1]
        assert calls == 1
        for key, (_, value) in list(cache._cache.items()):
            cache._cache[key] = (asyncio.get_running_loop().time(), value)
        await cache.fetch(session, "u", parser, fetch)
        assert calls == 2
        await cache.fetch(object(), "u", parser, fetch)
        await cache.fetch(session, "v", parser, fetch)
        await cache.fetch(session, "u", object(), fetch)
        assert calls == 5

    asyncio.run(run())


def test_none_and_errors_are_not_cached():
    async def run():
        cache, session, parser = mod.WeatherTransport(), object(), object()
        calls = 0

        async def fetch():
            nonlocal calls
            calls += 1
            if calls == 1:
                return None
            if calls == 2:
                raise RuntimeError("weather")
            return [calls]

        assert await cache.fetch(session, "u", parser, fetch) is None
        with pytest.raises(RuntimeError):
            await cache.fetch(session, "u", parser, fetch)
        assert await cache.fetch(session, "u", parser, fetch) == [3]
        assert calls == 3
        assert not cache._pending

    asyncio.run(run())


def test_cancel_one_waiter_then_cancel_last_cleans_owned_task():
    async def run():
        cache, session, parser = mod.WeatherTransport(), object(), object()
        started, stopped, finish = asyncio.Event(), asyncio.Event(), asyncio.Event()

        async def fetch():
            started.set()
            try:
                await finish.wait()
                return [1]
            finally:
                stopped.set()

        a = asyncio.create_task(cache.fetch(session, "u", parser, fetch))
        b = asyncio.create_task(cache.fetch(session, "u", parser, fetch))
        await started.wait()
        a.cancel()
        with pytest.raises(asyncio.CancelledError):
            await a
        assert not stopped.is_set()
        b.cancel()
        with pytest.raises(asyncio.CancelledError):
            await b
        assert stopped.is_set()
        assert not cache._cache and not cache._pending
        finish.set()
        assert await cache.fetch(session, "u", parser, fetch) == [1]

    asyncio.run(run())


def test_completed_cache_bound():
    async def run():
        cache, session, parser = mod.WeatherTransport(), object(), object()

        async def fetch():
            return [1]

        for i in range(mod.CACHE_ENTRIES + 4):
            await cache.fetch(session, str(i), parser, fetch)
        assert len(cache._cache) == mod.CACHE_ENTRIES

    asyncio.run(run())


def test_cancelled_consumer_does_not_cancel_survivor():
    async def run():
        cache, session, parser = mod.WeatherTransport(), object(), object()
        finish, started = asyncio.Event(), asyncio.Event()

        async def fetch():
            started.set()
            await finish.wait()
            return [7]

        a = asyncio.create_task(cache.fetch(session, "u", parser, fetch))
        b = asyncio.create_task(cache.fetch(session, "u", parser, fetch))
        await started.wait()
        a.cancel()
        with pytest.raises(asyncio.CancelledError):
            await a
        finish.set()
        assert await b == [7]
        assert await cache.fetch(session, "u", parser, fetch) == [7]

    asyncio.run(run())
