"""Massive (formerly Polygon.io) REST API polling client.

Polls the Massive snapshot endpoint on a configurable interval and writes
results to the shared PriceCache. Used when MASSIVE_API_KEY is set.

API docs: https://api.massive.com
Authentication: Bearer token in Authorization header
Primary endpoint: GET /v2/snapshot/locale/us/markets/stocks/tickers
"""

import asyncio
import logging

import httpx

from .cache import PriceCache
from .tickers import SUPPORTED_TICKERS

logger = logging.getLogger(__name__)

MASSIVE_BASE_URL = "https://api.massive.com"

# Rate limit guidance:
# Free tier: 5 req/min → poll every 15 seconds
# Paid tier: poll every 2-5 seconds
DEFAULT_POLL_INTERVAL = 15.0


class MassivePoller:
    """Polls the Massive snapshot API and writes to the PriceCache.

    Usage:
        cache = PriceCache()
        poller = MassivePoller(cache=cache, api_key="your-key")
        await poller.start()   # begins polling loop
        ...
        await poller.stop()    # cancels loop, closes HTTP client
    """

    def __init__(
        self,
        cache: PriceCache,
        api_key: str,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        base_url: str = MASSIVE_BASE_URL,
    ) -> None:
        self._cache = cache
        self._api_key = api_key
        self._poll_interval = poll_interval
        self._base_url = base_url
        self._client: httpx.AsyncClient | None = None
        self._task: asyncio.Task | None = None
        self._tickers = list(SUPPORTED_TICKERS.keys())

    async def start(self) -> None:
        """Open the HTTP client and begin the polling loop."""
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=10.0,
        )
        self._task = asyncio.create_task(self._poll_loop())
        logger.info(
            "MassivePoller started — polling %d tickers every %.1fs",
            len(self._tickers),
            self._poll_interval,
        )

    async def stop(self) -> None:
        """Cancel the polling loop and close the HTTP client."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._client:
            await self._client.aclose()
            self._client = None
        logger.info("MassivePoller stopped")

    def get_supported_tickers(self) -> list[str]:
        """Return all tickers in the supported universe."""
        return list(self._tickers)

    async def _poll_loop(self) -> None:
        """Main polling loop: fetch prices, wait, repeat."""
        while True:
            try:
                await self._fetch_and_update()
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "Massive API HTTP error %d: %s",
                    exc.response.status_code,
                    exc.response.text[:200],
                )
            except httpx.RequestError as exc:
                logger.warning("Massive API request error: %s", exc)
            except Exception as exc:
                logger.exception("Unexpected error in Massive poll loop: %s", exc)
            await asyncio.sleep(self._poll_interval)

    async def _fetch_and_update(self) -> None:
        """Fetch a price snapshot for all supported tickers and update the cache.

        Calls GET /v2/snapshot/locale/us/markets/stocks/tickers with the full
        ticker list. Extracts `lastTrade.p` as the current price for each ticker.
        """
        assert self._client is not None, "MassivePoller not started"

        resp = await self._client.get(
            "/v2/snapshot/locale/us/markets/stocks/tickers",
            params={"tickers": ",".join(self._tickers)},
        )
        resp.raise_for_status()
        data = resp.json()

        updated_count = 0
        for ticker_data in data.get("tickers", []):
            ticker = ticker_data.get("ticker")
            if ticker not in SUPPORTED_TICKERS:
                continue

            price = _extract_price(ticker_data)
            if price is not None and price > 0:
                self._cache.update(ticker, price)
                updated_count += 1

        logger.debug("Massive snapshot: updated %d tickers", updated_count)

    def parse_snapshot_response(self, data: dict) -> dict[str, float]:
        """Parse a Massive snapshot API response into a ticker->price mapping.

        Exposed as a public method for testability.

        Args:
            data: Parsed JSON response from the snapshot endpoint.

        Returns:
            Dict mapping ticker symbol to current price.
        """
        result: dict[str, float] = {}
        for ticker_data in data.get("tickers", []):
            ticker = ticker_data.get("ticker")
            if ticker not in SUPPORTED_TICKERS:
                continue
            price = _extract_price(ticker_data)
            if price is not None and price > 0:
                result[ticker] = price
        return result


def _extract_price(ticker_data: dict) -> float | None:
    """Extract the best available price from a Massive ticker snapshot.

    Preference order:
    1. lastTrade.p  — most recent trade price (real-time on paid tiers)
    2. day.c        — current session close/last (fallback)
    3. prevDay.c    — previous close (last resort for free-tier 403 scenarios)

    Returns None if no valid price is found.
    """
    last_trade = ticker_data.get("lastTrade", {})
    price = last_trade.get("p")
    if price is not None:
        return float(price)

    day = ticker_data.get("day", {})
    price = day.get("c")
    if price is not None:
        return float(price)

    prev_day = ticker_data.get("prevDay", {})
    price = prev_day.get("c")
    if price is not None:
        return float(price)

    return None
