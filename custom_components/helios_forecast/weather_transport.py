"""Bounded short-lived sharing of successful parsed weather requests.

Only work on the caller's event loop is shared. The last cancelled consumer owns
cancelling and settling the request; another consumer never inherits that cancel.
"""

from __future__ import annotations

import asyncio
import copy
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable, Coroutine, TypeVar

_T = TypeVar("_T")
CACHE_SECONDS = 300.0
CACHE_ENTRIES = 32


@dataclass
class _Flight:
    task: asyncio.Task
    users: int = 0


class WeatherTransport:
    """One process-local cache; completed values and pending tasks have separate lifetimes."""

    def __init__(self) -> None:
        self._cache: OrderedDict[tuple, tuple[float, Any]] = OrderedDict()
        self._pending: dict[tuple, _Flight] = {}

    async def fetch(
        self, session: Any, url: str, parser: Any, fetch: Callable[[], Coroutine[Any, Any, _T | None]]
    ) -> _T | None:
        loop = asyncio.get_running_loop()
        key = (loop, session, url, parser)
        now = loop.time()
        # Expired entries retain neither sessions nor event loops indefinitely.
        for old in [k for k, (until, _) in self._cache.items() if until <= now or k[0] is not loop]:
            del self._cache[old]
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            return copy.deepcopy(cached[1])
        flight = self._pending.get(key)
        if flight is None:
            flight = _Flight(loop.create_task(fetch()))
            self._pending[key] = flight
        flight.users += 1
        try:
            result = await asyncio.shield(flight.task)
            if result is not None and key not in self._cache:
                self._cache[key] = (loop.time() + CACHE_SECONDS, copy.deepcopy(result))
                while len(self._cache) > CACHE_ENTRIES:
                    self._cache.popitem(last=False)
            return copy.deepcopy(result)
        finally:
            flight.users -= 1
            if flight.users == 0:
                self._pending.pop(key, None)
                if not flight.task.done():
                    flight.task.cancel()
                    try:
                        await flight.task
                    except asyncio.CancelledError:
                        pass


_SHARED = WeatherTransport()


async def coalesced_fetch(
    session: Any, url: str, parser: Any, fetch: Callable[[], Coroutine[Any, Any, _T | None]]
) -> _T | None:
    """Share identical successful work without sharing mutable returned objects."""
    return await _SHARED.fetch(session, url, parser, fetch)
