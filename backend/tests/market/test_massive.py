"""Unit tests for market/massive.py — MassivePoller and response parsing."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from market.cache import PriceCache
from market.massive import (
    DEFAULT_POLL_INTERVAL,
    MASSIVE_BASE_URL,
    MassivePoller,
    _extract_price,
)
from market.tickers import SUPPORTED_TICKERS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_ticker_snapshot(
    ticker: str,
    last_trade_price: float | None = None,
    day_close: float | None = None,
    prev_day_close: float | None = None,
) -> dict:
    """Build a fake Massive ticker snapshot payload."""
    result: dict = {"ticker": ticker}
    if last_trade_price is not None:
        result["lastTrade"] = {"p": last_trade_price, "s": 100, "t": 1702483260000}
    if day_close is not None:
        result["day"] = {"c": day_close, "o": day_close, "h": day_close, "l": day_close, "v": 1000}
    if prev_day_close is not None:
        result["prevDay"] = {"c": prev_day_close}
    return result


def make_snapshot_response(tickers_data: list[dict]) -> dict:
    """Wrap ticker snapshots in the Massive API envelope."""
    return {"count": len(tickers_data), "status": "OK", "tickers": tickers_data}


# ---------------------------------------------------------------------------
# _extract_price()
# ---------------------------------------------------------------------------


class TestExtractPrice:
    def test_prefers_last_trade_price(self):
        data = make_ticker_snapshot(
            "AAPL",
            last_trade_price=191.0,
            day_close=192.0,
            prev_day_close=189.0,
        )
        assert _extract_price(data) == 191.0

    def test_falls_back_to_day_close(self):
        data = make_ticker_snapshot("AAPL", day_close=192.0, prev_day_close=189.0)
        assert _extract_price(data) == 192.0

    def test_falls_back_to_prev_day_close(self):
        data = make_ticker_snapshot("AAPL", prev_day_close=189.0)
        assert _extract_price(data) == 189.0

    def test_returns_none_when_no_price(self):
        assert _extract_price({"ticker": "AAPL"}) is None

    def test_returns_none_for_empty_dict(self):
        assert _extract_price({}) is None

    def test_returns_float(self):
        data = make_ticker_snapshot("AAPL", last_trade_price=191)
        result = _extract_price(data)
        assert isinstance(result, float)

    def test_handles_integer_price(self):
        data = {"ticker": "AAPL", "lastTrade": {"p": 191}}
        assert _extract_price(data) == 191.0


# ---------------------------------------------------------------------------
# MassivePoller initialization
# ---------------------------------------------------------------------------


class TestMassivePollerInit:
    def test_default_poll_interval(self):
        cache = PriceCache()
        poller = MassivePoller(cache=cache, api_key="test-key")
        assert poller._poll_interval == DEFAULT_POLL_INTERVAL

    def test_custom_poll_interval(self):
        cache = PriceCache()
        poller = MassivePoller(cache=cache, api_key="test-key", poll_interval=5.0)
        assert poller._poll_interval == 5.0

    def test_tickers_are_all_supported(self):
        cache = PriceCache()
        poller = MassivePoller(cache=cache, api_key="test-key")
        assert set(poller._tickers) == set(SUPPORTED_TICKERS.keys())

    def test_client_is_none_before_start(self):
        cache = PriceCache()
        poller = MassivePoller(cache=cache, api_key="test-key")
        assert poller._client is None

    def test_task_is_none_before_start(self):
        cache = PriceCache()
        poller = MassivePoller(cache=cache, api_key="test-key")
        assert poller._task is None

    def test_get_supported_tickers(self):
        cache = PriceCache()
        poller = MassivePoller(cache=cache, api_key="test-key")
        tickers = poller.get_supported_tickers()
        assert isinstance(tickers, list)
        assert set(tickers) == set(SUPPORTED_TICKERS.keys())


# ---------------------------------------------------------------------------
# MassivePoller.start() / stop()
# ---------------------------------------------------------------------------


class TestMassivePollerLifecycle:
    @pytest.mark.asyncio
    async def test_start_creates_http_client(self):
        cache = PriceCache()
        poller = MassivePoller(cache=cache, api_key="test-key")
        # Patch the poll loop so it doesn't actually try to connect
        with patch.object(poller, "_poll_loop", return_value=AsyncMock()):
            await poller.start()
            try:
                assert poller._client is not None
                assert isinstance(poller._client, httpx.AsyncClient)
            finally:
                await poller.stop()

    @pytest.mark.asyncio
    async def test_start_creates_background_task(self):
        cache = PriceCache()
        poller = MassivePoller(cache=cache, api_key="test-key")

        async def noop_loop():
            await asyncio.sleep(9999)

        with patch.object(poller, "_poll_loop", side_effect=noop_loop):
            await poller.start()
            try:
                assert poller._task is not None
                assert not poller._task.done()
            finally:
                await poller.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_task(self):
        cache = PriceCache()
        poller = MassivePoller(cache=cache, api_key="test-key")

        async def noop_loop():
            await asyncio.sleep(9999)

        with patch.object(poller, "_poll_loop", side_effect=noop_loop):
            await poller.start()
            task = poller._task
            await poller.stop()
            assert task.done()
            assert poller._task is None

    @pytest.mark.asyncio
    async def test_stop_closes_http_client(self):
        cache = PriceCache()
        poller = MassivePoller(cache=cache, api_key="test-key")

        async def noop_loop():
            await asyncio.sleep(9999)

        with patch.object(poller, "_poll_loop", side_effect=noop_loop):
            await poller.start()
            await poller.stop()
            assert poller._client is None

    @pytest.mark.asyncio
    async def test_stop_is_idempotent_when_not_started(self):
        cache = PriceCache()
        poller = MassivePoller(cache=cache, api_key="test-key")
        # Should not raise
        await poller.stop()

    @pytest.mark.asyncio
    async def test_client_uses_bearer_auth(self):
        cache = PriceCache()
        api_key = "super-secret-key"
        poller = MassivePoller(cache=cache, api_key=api_key)

        async def noop_loop():
            await asyncio.sleep(9999)

        with patch.object(poller, "_poll_loop", side_effect=noop_loop):
            await poller.start()
            try:
                auth_header = poller._client.headers.get("authorization")
                assert auth_header == f"Bearer {api_key}"
            finally:
                await poller.stop()


# ---------------------------------------------------------------------------
# MassivePoller.parse_snapshot_response()
# ---------------------------------------------------------------------------


class TestParseSnapshotResponse:
    def setup_method(self):
        self.cache = PriceCache()
        self.poller = MassivePoller(cache=self.cache, api_key="test-key")

    def test_parses_last_trade_price(self):
        data = make_snapshot_response([
            make_ticker_snapshot("AAPL", last_trade_price=191.0),
        ])
        result = self.poller.parse_snapshot_response(data)
        assert result["AAPL"] == 191.0

    def test_parses_multiple_tickers(self):
        data = make_snapshot_response([
            make_ticker_snapshot("AAPL", last_trade_price=191.0),
            make_ticker_snapshot("TSLA", last_trade_price=251.0),
            make_ticker_snapshot("MSFT", last_trade_price=421.0),
        ])
        result = self.poller.parse_snapshot_response(data)
        assert result["AAPL"] == 191.0
        assert result["TSLA"] == 251.0
        assert result["MSFT"] == 421.0

    def test_skips_unsupported_tickers(self):
        data = make_snapshot_response([
            make_ticker_snapshot("AAPL", last_trade_price=191.0),
            make_ticker_snapshot("ZZZZ", last_trade_price=50.0),
        ])
        result = self.poller.parse_snapshot_response(data)
        assert "AAPL" in result
        assert "ZZZZ" not in result

    def test_skips_tickers_with_zero_price(self):
        data = make_snapshot_response([
            make_ticker_snapshot("AAPL", last_trade_price=0.0),
        ])
        result = self.poller.parse_snapshot_response(data)
        assert "AAPL" not in result

    def test_skips_tickers_with_no_price(self):
        data = make_snapshot_response([
            {"ticker": "AAPL"},  # no price fields
        ])
        result = self.poller.parse_snapshot_response(data)
        assert "AAPL" not in result

    def test_empty_tickers_list(self):
        data = make_snapshot_response([])
        result = self.poller.parse_snapshot_response(data)
        assert result == {}

    def test_missing_tickers_key(self):
        result = self.poller.parse_snapshot_response({"status": "OK", "count": 0})
        assert result == {}

    def test_uses_day_close_fallback(self):
        data = make_snapshot_response([
            make_ticker_snapshot("AAPL", day_close=192.0),
        ])
        result = self.poller.parse_snapshot_response(data)
        assert result["AAPL"] == 192.0

    def test_uses_prev_day_close_fallback(self):
        data = make_snapshot_response([
            make_ticker_snapshot("AAPL", prev_day_close=189.0),
        ])
        result = self.poller.parse_snapshot_response(data)
        assert result["AAPL"] == 189.0


# ---------------------------------------------------------------------------
# MassivePoller._fetch_and_update()
# ---------------------------------------------------------------------------


class TestFetchAndUpdate:
    @pytest.mark.asyncio
    async def test_updates_cache_with_fetched_prices(self):
        cache = PriceCache()
        poller = MassivePoller(cache=cache, api_key="test-key")

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = make_snapshot_response([
            make_ticker_snapshot("AAPL", last_trade_price=191.0),
            make_ticker_snapshot("TSLA", last_trade_price=251.0),
        ])

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        poller._client = mock_client

        await poller._fetch_and_update()

        assert cache.get_price("AAPL") == 191.0
        assert cache.get_price("TSLA") == 251.0

    @pytest.mark.asyncio
    async def test_calls_snapshot_endpoint(self):
        cache = PriceCache()
        poller = MassivePoller(cache=cache, api_key="test-key")

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = make_snapshot_response([])

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        poller._client = mock_client

        await poller._fetch_and_update()

        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert "/v2/snapshot/locale/us/markets/stocks/tickers" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_does_not_crash_on_empty_response(self):
        cache = PriceCache()
        poller = MassivePoller(cache=cache, api_key="test-key")

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"status": "OK", "tickers": []}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        poller._client = mock_client

        # Should not raise
        await poller._fetch_and_update()


# ---------------------------------------------------------------------------
# MassivePoller._poll_loop() error handling
# ---------------------------------------------------------------------------


class TestPollLoopErrorHandling:
    @pytest.mark.asyncio
    async def test_continues_after_http_error(self):
        """The poll loop should not crash on HTTP errors — it should log and retry."""
        cache = PriceCache()
        poller = MassivePoller(cache=cache, api_key="test-key", poll_interval=0.05)

        call_count = 0

        async def flaky_fetch():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                mock_resp = MagicMock()
                mock_resp.status_code = 429
                mock_resp.text = "Rate limited"
                raise httpx.HTTPStatusError("rate limited", request=MagicMock(), response=mock_resp)
            # On 3rd+ call, succeed with no-op
            pass

        with patch.object(poller, "_fetch_and_update", side_effect=flaky_fetch):
            poller._client = MagicMock()
            poller._client.aclose = AsyncMock()
            poller._task = asyncio.create_task(poller._poll_loop())
            await asyncio.sleep(0.2)
            poller._task.cancel()
            try:
                await poller._task
            except asyncio.CancelledError:
                pass

        assert call_count >= 3

    @pytest.mark.asyncio
    async def test_continues_after_request_error(self):
        """The poll loop should not crash on network errors."""
        cache = PriceCache()
        poller = MassivePoller(cache=cache, api_key="test-key", poll_interval=0.05)

        call_count = 0

        async def flaky_fetch():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.RequestError("connection refused")

        with patch.object(poller, "_fetch_and_update", side_effect=flaky_fetch):
            poller._client = MagicMock()
            poller._client.aclose = AsyncMock()
            poller._task = asyncio.create_task(poller._poll_loop())
            await asyncio.sleep(0.2)
            poller._task.cancel()
            try:
                await poller._task
            except asyncio.CancelledError:
                pass

        assert call_count >= 3
