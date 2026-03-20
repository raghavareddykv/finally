# Market Data Interface Design

This document defines the unified Python interface for retrieving stock prices in the FinAlly backend. The interface abstracts over two implementations — a **market simulator** (default) and the **Massive API** (when `MASSIVE_API_KEY` is set).

## Design Principle

All downstream code (SSE streaming, trade execution, portfolio valuation) interacts only with the **PriceCache**. The cache is populated by exactly one **MarketDataProvider** — either the simulator or the Massive poller. Downstream code never knows or cares which provider is active.

```
┌──────────────────────┐     ┌────────────┐     ┌──────────────────┐
│  MarketSimulator     │────▶│            │◀────│ SSE /api/stream  │
│  (or MassivePoller)  │     │ PriceCache │◀────│ Trade execution  │
│                      │     │            │◀────│ Portfolio valuation│
└──────────────────────┘     └────────────┘     └──────────────────┘
         writes                  reads
```

---

## PriceCache

The shared in-memory cache that holds the latest price state for every active ticker. A plain Python dict — safe for single-process asyncio (cooperative scheduling, no concurrent writes).

```python
# backend/market/cache.py

from dataclasses import dataclass
import time


@dataclass(slots=True)
class TickerPrice:
    """Immutable snapshot of a ticker's current price state."""
    ticker: str
    price: float
    previous_price: float
    timestamp: float
    direction: str  # "up" | "down" | "flat"


class PriceCache:
    """In-memory latest-price cache. One entry per ticker."""

    def __init__(self) -> None:
        self._prices: dict[str, TickerPrice] = {}

    def update(self, ticker: str, new_price: float) -> TickerPrice:
        """Write a new price. Computes direction from previous value."""
        now = time.time()
        prev = self._prices.get(ticker)
        previous_price = prev.price if prev else new_price

        if new_price > previous_price:
            direction = "up"
        elif new_price < previous_price:
            direction = "down"
        else:
            direction = "flat"

        entry = TickerPrice(
            ticker=ticker,
            price=round(new_price, 2),
            previous_price=round(previous_price, 2),
            timestamp=now,
            direction=direction,
        )
        self._prices[ticker] = entry
        return entry

    def get(self, ticker: str) -> TickerPrice | None:
        return self._prices.get(ticker)

    def get_many(self, tickers: list[str]) -> list[TickerPrice]:
        return [self._prices[t] for t in tickers if t in self._prices]

    def get_price(self, ticker: str) -> float | None:
        """Convenience: just the price float, or None."""
        entry = self._prices.get(ticker)
        return entry.price if entry else None
```

---

## MarketDataProvider Protocol

Both the simulator and Massive poller conform to this protocol. This is not an ABC — it's a structural typing contract via `Protocol` so implementations don't need to inherit from anything.

```python
# backend/market/provider.py

from typing import Protocol


class MarketDataProvider(Protocol):
    """Structural contract for market data providers."""

    async def start(self) -> None:
        """Begin generating/fetching prices. Called once at app startup."""
        ...

    async def stop(self) -> None:
        """Clean shutdown. Called once at app shutdown."""
        ...

    def get_supported_tickers(self) -> list[str]:
        """Return the list of tickers this provider knows about."""
        ...
```

Both providers:
- Write to the shared `PriceCache` instance on their own schedule
- Run as asyncio background tasks (created in `start()`, cancelled in `stop()`)
- Are instantiated with a reference to the `PriceCache`

---

## Factory Function

A single factory selects the provider based on environment configuration.

```python
# backend/market/__init__.py

import os
from .cache import PriceCache
from .simulator import MarketSimulator
from .massive import MassivePoller


def create_market_provider(cache: PriceCache) -> MarketSimulator | MassivePoller:
    """Create the appropriate market data provider based on environment."""
    api_key = os.environ.get("MASSIVE_API_KEY", "").strip()

    if api_key:
        return MassivePoller(cache=cache, api_key=api_key)
    else:
        return MarketSimulator(cache=cache)
```

---

## Provider: MarketSimulator

See [MARKET_SIMULATOR.md](./MARKET_SIMULATOR.md) for full details.

**Summary:** Generates prices using geometric Brownian motion (GBM) with per-ticker drift/volatility, occasional jump events, and soft mean reversion. Updates all tickers every 500ms. Zero external dependencies.

```python
# backend/market/simulator.py

class MarketSimulator:
    def __init__(self, cache: PriceCache) -> None: ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    def get_supported_tickers(self) -> list[str]: ...
```

---

## Provider: MassivePoller

Polls the Massive (Polygon.io) REST API snapshot endpoint on a configurable interval and writes results to the PriceCache.

```python
# backend/market/massive.py

import asyncio
import httpx
from .cache import PriceCache

MASSIVE_BASE_URL = "https://api.massive.com"


class MassivePoller:
    """Polls the Massive snapshot API and writes to the PriceCache."""

    def __init__(
        self,
        cache: PriceCache,
        api_key: str,
        poll_interval: float = 15.0,  # 15s default (free tier safe)
    ) -> None:
        self._cache = cache
        self._api_key = api_key
        self._poll_interval = poll_interval
        self._client: httpx.AsyncClient | None = None
        self._task: asyncio.Task | None = None
        self._tickers = list(SUPPORTED_TICKERS.keys())  # from shared ticker universe

    async def start(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=MASSIVE_BASE_URL,
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=10.0,
        )
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._client:
            await self._client.aclose()

    def get_supported_tickers(self) -> list[str]:
        return self._tickers

    async def _poll_loop(self) -> None:
        while True:
            try:
                await self._fetch_and_update()
            except httpx.HTTPStatusError as e:
                # Log and continue — don't crash the loop
                print(f"Massive API HTTP error: {e.response.status_code}")
            except httpx.RequestError as e:
                print(f"Massive API request error: {e}")
            await asyncio.sleep(self._poll_interval)

    async def _fetch_and_update(self) -> None:
        """Fetch snapshot for all watched tickers and update cache."""
        # Get the current watchlist from DB (or use full universe)
        tickers = self._tickers  # Could be refined to only watched tickers

        resp = await self._client.get(
            "/v2/snapshot/locale/us/markets/stocks/tickers",
            params={"tickers": ",".join(tickers)},
        )
        resp.raise_for_status()
        data = resp.json()

        for t in data.get("tickers", []):
            ticker = t["ticker"]
            last_trade = t.get("lastTrade", {})
            price = last_trade.get("p")
            if price is not None and ticker in SUPPORTED_TICKERS:
                self._cache.update(ticker, price)
```

---

## Supported Ticker Universe

A shared constant used by both providers, the API validation layer, and the frontend ticker dropdown. Defined once, imported everywhere.

```python
# backend/market/tickers.py

SUPPORTED_TICKERS: dict[str, float] = {
    # Tech
    "AAPL": 190.0,
    "GOOGL": 175.0,
    "MSFT": 420.0,
    "AMZN": 185.0,
    "TSLA": 250.0,
    "NVDA": 880.0,
    "META": 500.0,
    "NFLX": 620.0,
    "AMD": 160.0,
    "INTC": 45.0,
    "CRM": 280.0,
    "ORCL": 125.0,
    "ADBE": 560.0,
    "CSCO": 50.0,
    "QCOM": 170.0,
    "AVGO": 1350.0,
    "UBER": 75.0,
    "SQ": 80.0,
    "SHOP": 75.0,
    "PYPL": 65.0,

    # Finance
    "JPM": 195.0,
    "V": 280.0,
    "MA": 460.0,
    "BAC": 35.0,
    "GS": 410.0,
    "MS": 95.0,
    "BLK": 810.0,
    "AXP": 220.0,

    # Healthcare
    "JNJ": 155.0,
    "PFE": 28.0,
    "UNH": 520.0,
    "MRK": 125.0,
    "ABBV": 170.0,
    "LLY": 750.0,

    # Consumer
    "KO": 60.0,
    "PEP": 170.0,
    "WMT": 165.0,
    "COST": 720.0,
    "MCD": 290.0,
    "NKE": 105.0,
    "SBUX": 95.0,
    "DIS": 115.0,

    # Industrial / Energy / Other
    "BA": 190.0,
    "CAT": 330.0,
    "XOM": 105.0,
    "CVX": 155.0,
    "GE": 160.0,
    "UPS": 145.0,
    "HD": 370.0,
    "LMT": 450.0,
}
"""Mapping of supported ticker symbols to seed prices (approximate USD).

Seed prices are used by the simulator as starting values.
The Massive poller uses only the keys (valid ticker list).
This dict is also the single source of truth for ticker validation
across the API (trade requests, watchlist additions, etc.).
"""
```

---

## Integration with FastAPI Lifespan

```python
# backend/main.py (relevant excerpt)

from contextlib import asynccontextmanager
from fastapi import FastAPI
from market import create_market_provider
from market.cache import PriceCache

price_cache = PriceCache()
provider = create_market_provider(price_cache)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await provider.start()
    yield
    await provider.stop()

app = FastAPI(lifespan=lifespan)
```

---

## SSE Endpoint (Consumer Pattern)

The SSE endpoint reads from the PriceCache on a fixed cadence. It does not know whether prices come from the simulator or Massive API.

```python
# backend/routes/stream.py (sketch)

from sse_starlette.sse import EventSourceResponse
import json, asyncio

@app.get("/api/stream/prices")
async def stream_prices():
    async def generate():
        while True:
            watchlist = await get_user_watchlist()  # from DB
            prices = price_cache.get_many(watchlist)
            for p in prices:
                yield {
                    "event": "price",
                    "data": json.dumps({
                        "ticker": p.ticker,
                        "price": p.price,
                        "previousPrice": p.previous_price,
                        "timestamp": p.timestamp,
                        "direction": p.direction,
                    }),
                }
            await asyncio.sleep(0.5)
    return EventSourceResponse(generate())
```

---

## Trade Execution (Consumer Pattern)

Trade execution reads the current price from the cache at the moment of the trade.

```python
# backend/routes/portfolio.py (sketch)

@app.post("/api/portfolio/trade")
async def execute_trade(request: TradeRequest):
    current = price_cache.get_price(request.ticker)
    if current is None:
        raise HTTPException(400, detail="No price available for ticker")

    # Execute at current cache price (market order, instant fill)
    ...
```

---

## File Layout Summary

```
backend/
  market/
    __init__.py       # create_market_provider() factory
    cache.py          # PriceCache + TickerPrice
    provider.py       # MarketDataProvider Protocol
    tickers.py        # SUPPORTED_TICKERS constant
    simulator.py      # MarketSimulator (GBM-based)
    massive.py        # MassivePoller (REST API client)
```
