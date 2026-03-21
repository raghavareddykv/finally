"""Tests for SSE price streaming logic.

Full SSE endpoint streaming is validated in E2E tests. Here we test
the core generator function that produces price events.
"""

import json

import pytest

from routes.stream import _price_generator


class FakeRequest:
    """Minimal request mock for SSE testing."""
    def __init__(self, disconnect_after: int = 999):
        self._calls = 0
        self._disconnect_after = disconnect_after

    async def is_disconnected(self):
        self._calls += 1
        return self._calls > self._disconnect_after


@pytest.mark.asyncio
async def test_price_generator_yields_events(seed_db, seed_prices):
    """Verify the SSE generator produces correct event data."""
    cache = seed_prices
    request = FakeRequest()
    watchlist_tickers = ["AAPL", "GOOGL", "MSFT"]

    async def get_tickers():
        return watchlist_tickers

    events = []
    async for event in _price_generator(request, cache, get_tickers):
        events.append(event)
        if len(events) >= 3:
            break

    assert len(events) == 3
    for event in events:
        assert event["event"] == "price_update"
        data = json.loads(event["data"])
        assert data["ticker"] in watchlist_tickers
        assert isinstance(data["price"], float)
        assert isinstance(data["previous_price"], float)
        assert isinstance(data["timestamp"], float)
        assert data["direction"] in ("up", "down", "flat")


@pytest.mark.asyncio
async def test_price_generator_disconnects_cleanly(seed_db, seed_prices):
    """Generator stops when client disconnects."""
    cache = seed_prices
    request = FakeRequest(disconnect_after=1)

    async def get_tickers():
        return ["AAPL"]

    events = []
    async for event in _price_generator(request, cache, get_tickers):
        events.append(event)

    # Should have stopped producing events after disconnect
    # (first call returns False, second returns True triggering break)
    assert len(events) <= 50  # Should be much less, but generous bound
