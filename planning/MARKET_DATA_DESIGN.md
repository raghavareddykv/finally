# Market Data Backend — Implementation Design

This document is the comprehensive implementation guide for the FinAlly market data backend. It covers every file, every class, every method, and every line of logic needed to build the `backend/market/` package from scratch. It consolidates and extends the designs from `MARKET_INTERFACE.md`, `MARKET_SIMULATOR.md`, and `MASSIVE_API.md` into a single, copy-paste-ready reference.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [File Layout](#2-file-layout)
3. [Module: `tickers.py` — Supported Ticker Universe](#3-module-tickerspy--supported-ticker-universe)
4. [Module: `cache.py` — PriceCache & TickerPrice](#4-module-cachepy--pricecache--tickerprice)
5. [Module: `provider.py` — MarketDataProvider Protocol](#5-module-providerpy--marketdataprovider-protocol)
6. [Module: `simulator.py` — MarketSimulator (GBM)](#6-module-simulatorpy--marketsimulator-gbm)
7. [Module: `massive.py` — MassivePoller (REST API)](#7-module-massivepy--massivepoller-rest-api)
8. [Module: `__init__.py` — Factory & Public API](#8-module-__init__py--factory--public-api)
9. [Integration with FastAPI](#9-integration-with-fastapi)
10. [SSE Streaming Consumer](#10-sse-streaming-consumer)
11. [Trade Execution Consumer](#11-trade-execution-consumer)
12. [Testing Strategy](#12-testing-strategy)
13. [Dependencies](#13-dependencies)

---

## 1. Architecture Overview

### Data Flow

```
┌──────────────────────────┐
│  MarketSimulator         │     ┌────────────┐     ┌───────────────────┐
│  (GBM, 500ms ticks)     │────▶│            │◀────│ SSE /api/stream   │
│  OR                      │     │ PriceCache │◀────│ Trade execution   │
│  MassivePoller           │     │            │◀────│ Portfolio value   │
│  (REST API, 15s polls)   │     │            │◀────│ LLM context       │
└──────────────────────────┘     └────────────┘     └───────────────────┘
         writes only                  reads only
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Protocol (structural typing) over ABC | Providers don't inherit from anything; decoupled, testable |
| Single PriceCache dict | Asyncio is cooperative — no locks needed for single-process |
| Factory function over DI | One env var check at startup; no framework needed |
| Provider writes, consumers read | Unidirectional data flow; cache is the only shared state |
| Prices rounded to 2 decimals | USD convention; avoids floating-point display noise |

### Lifecycle

1. FastAPI `lifespan` creates `PriceCache` and calls `create_market_provider(cache)`
2. `provider.start()` initializes prices and spawns a background `asyncio.Task`
3. The task writes to the cache every 500ms (simulator) or 15s (Massive)
4. SSE endpoints and trade handlers read from the cache
5. `provider.stop()` cancels the task and cleans up on shutdown

---

## 2. File Layout

```
backend/
  market/
    __init__.py       # create_market_provider() factory + public re-exports
    cache.py          # PriceCache + TickerPrice dataclass
    provider.py       # MarketDataProvider Protocol (structural typing contract)
    tickers.py        # SUPPORTED_TICKERS dict — single source of truth
    simulator.py      # MarketSimulator — GBM with jumps and mean reversion
    massive.py        # MassivePoller — REST API polling client
  tests/
    market/
      __init__.py
      test_cache.py
      test_simulator.py
      test_massive.py
      test_provider.py
```

---

## 3. Module: `tickers.py` — Supported Ticker Universe

This is the single source of truth for valid ticker symbols and seed prices. Used by:
- **Simulator**: starting prices for GBM
- **MassivePoller**: list of tickers to poll
- **API validation**: trade requests, watchlist additions
- **Frontend**: ticker dropdown population

### Complete Implementation

```python
# backend/market/tickers.py

"""Supported ticker universe with seed prices.

This is the single source of truth for:
- Valid ticker symbols (API validation, watchlist, trade requests)
- Seed prices (simulator starting values)
- Ticker universe for the Massive poller
"""

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
```

**48 tickers** across 6 sectors. Seed prices are approximate real-world values as of late 2024.

### Usage Examples

```python
from market.tickers import SUPPORTED_TICKERS

# Validate a ticker
def is_valid_ticker(ticker: str) -> bool:
    return ticker in SUPPORTED_TICKERS

# Get seed price
seed = SUPPORTED_TICKERS["AAPL"]  # 190.0

# Get all ticker symbols
all_symbols = list(SUPPORTED_TICKERS.keys())  # ["AAPL", "GOOGL", ...]
```

---

## 4. Module: `cache.py` — PriceCache & TickerPrice

The PriceCache is the central shared state between providers (writers) and consumers (readers). It holds one `TickerPrice` entry per ticker — the latest price, the previous price, a timestamp, and the direction of change.

### Complete Implementation

```python
# backend/market/cache.py

"""In-memory price cache — the shared state between market data providers and consumers."""

import time
from dataclasses import dataclass


@dataclass(slots=True)
class TickerPrice:
    """Immutable snapshot of a ticker's current price state."""

    ticker: str
    price: float
    previous_price: float
    timestamp: float
    direction: str  # "up" | "down" | "flat"


class PriceCache:
    """In-memory latest-price cache. One entry per ticker.

    Safe for single-process asyncio (cooperative scheduling, no concurrent writes).
    """

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
        """Return the TickerPrice for a ticker, or None if not in cache."""
        return self._prices.get(ticker)

    def get_many(self, tickers: list[str]) -> list[TickerPrice]:
        """Return TickerPrice entries for all tickers present in the cache."""
        return [self._prices[t] for t in tickers if t in self._prices]

    def get_price(self, ticker: str) -> float | None:
        """Convenience: just the price float, or None if not in cache."""
        entry = self._prices.get(ticker)
        return entry.price if entry else None

    def all_tickers(self) -> list[str]:
        """Return all tickers currently in the cache."""
        return list(self._prices.keys())
```

### Design Details

**`TickerPrice` dataclass:**
- `slots=True` for memory efficiency — 48 tickers × frequent updates
- Stores both `price` and `previous_price` so the SSE stream can send both (frontend uses them for flash animations)
- `direction` is `"up"`, `"down"`, or `"flat"` — computed on each update by comparing new vs. previous price
- On the very first update for a ticker, `previous_price` equals `new_price`, so `direction` is `"flat"`

**`PriceCache.update()` flow:**
1. Look up previous entry for this ticker
2. If exists, use `prev.price` as `previous_price`; otherwise `previous_price = new_price`
3. Compare `new_price` to `previous_price` to determine direction
4. Round both prices to 2 decimal places (USD convention)
5. Store the new `TickerPrice` entry, overwriting the old one
6. Return the entry (callers may want the direction/timestamp)

**Thread safety:** Not needed. Python asyncio uses cooperative scheduling — only one coroutine runs at a time per event loop. The provider's background task and the SSE endpoint run on the same loop, so there are never concurrent writes.

### Usage Examples

```python
cache = PriceCache()

# Provider writes a price
entry = cache.update("AAPL", 191.50)
# entry.direction == "flat" (first update)

entry = cache.update("AAPL", 192.00)
# entry.direction == "up", entry.previous_price == 191.50

# Consumer reads latest price
price = cache.get_price("AAPL")       # 192.0
entry = cache.get("AAPL")             # full TickerPrice object

# SSE endpoint reads multiple tickers
watchlist = ["AAPL", "TSLA", "NVDA"]
entries = cache.get_many(watchlist)    # list of TickerPrice for present tickers
```

---

## 5. Module: `provider.py` — MarketDataProvider Protocol

The protocol defines the structural contract that both providers satisfy. Using `typing.Protocol` means providers don't inherit from anything — they just need to have the right method signatures.

### Complete Implementation

```python
# backend/market/provider.py

"""MarketDataProvider protocol — structural typing contract for market data providers.

Both MarketSimulator and MassivePoller conform to this protocol.
Downstream code (SSE, trade execution, portfolio valuation) depends only on PriceCache,
not on any specific provider.
"""

from typing import Protocol


class MarketDataProvider(Protocol):
    """Structural contract for market data providers.

    Implementations must be instantiated with a reference to a PriceCache
    and write updated prices into it on their own schedule.
    """

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

### Protocol Conformance

Neither `MarketSimulator` nor `MassivePoller` inherits from `MarketDataProvider`. Python's structural typing checks conformance at type-checking time (mypy/pyright):

```python
# This works because both classes have start(), stop(), get_supported_tickers()
provider: MarketDataProvider = MarketSimulator(cache)  # OK
provider: MarketDataProvider = MassivePoller(cache, key)  # OK
```

The factory function returns `MarketSimulator | MassivePoller` (a union) rather than `MarketDataProvider` to avoid runtime Protocol instantiation issues. Callers that need to be provider-agnostic can type-annotate with `MarketDataProvider`.

---

## 6. Module: `simulator.py` — MarketSimulator (GBM)

The simulator is the default market data provider. It generates realistic price movements using geometric Brownian motion with jump events and mean reversion.

### Mathematical Model

#### Core GBM Equation (Exact Discrete Form)

```
S(t + dt) = S(t) × exp((μ_adj - σ²/2) × dt + σ × √dt × Z)
```

Where:
- `S(t)` = current price
- `μ_adj` = adjusted drift (after mean reversion)
- `σ` = annualized volatility
- `dt` = time step as fraction of a year
- `Z ~ N(0, 1)` = standard normal random draw

The `- σ²/2` term is the **Ito correction** — it ensures the expected return equals μ, not μ + σ²/2.

The **exponential form guarantees prices stay positive** without any clamping for negativity.

#### Time Step

```
Trading year = 252 days × 6.5 hours/day = 5,896,800 seconds
dt = 0.5 / 5,896,800 ≈ 8.478 × 10⁻⁸
√dt ≈ 2.912 × 10⁻⁴
```

With this tiny dt, each tick produces ~0.01–0.05% price change for typical volatilities — realistic.

#### Mean Reversion (Soft)

Prevents prices from wandering too far from seed over long demo sessions:

```
μ_adj = μ - κ × ln(S / S₀)
```

Where `κ = 0.1` (annualized) and `S₀` = seed price.

- Price > seed → `ln(S/S₀) > 0` → drift decreases → price pulled back down
- Price < seed → `ln(S/S₀) < 0` → drift increases → price pulled back up
- Prices wander ±20–30% from seed but slowly revert over hours

#### Jump Events (Merton Jump-Diffusion)

Occasional sudden 2–5% moves for visual drama:

```
On each tick, with probability λ = 0.0002:
    jump = N(0, 0.03)  # log-space jump
```

This yields ~1 jump per 83 minutes per ticker, or about **one visible jump every ~100 seconds across the full 48-ticker universe**.

### Per-Ticker Parameter Assignment

| Category | Tickers | Drift | Volatility | Character |
|----------|---------|-------|------------|-----------|
| High-vol growth | TSLA, NVDA, AMD, SHOP, SQ | 0.04 | 0.50 | Most movement |
| Med-high vol | META, NFLX, AMZN, ADBE, CRM, UBER, BA, DIS, PYPL | 0.05 | 0.32 | Visible movement |
| Med vol (large-cap tech) | AAPL, GOOGL, MSFT, ORCL, QCOM, AVGO, INTC, CSCO | 0.05 | 0.25 | Steady |
| Financial | JPM, BAC, GS, MS, AXP, BLK | 0.04 | 0.22 | Moderate |
| Payments | V, MA | 0.04 | 0.18 | Low vol |
| Healthcare | JNJ, PFE, UNH, MRK, ABBV, LLY | 0.03 | 0.22 | Moderate |
| Consumer defensive | KO, PEP, WMT, COST, MCD, NKE, SBUX | 0.03 | 0.18 | Least movement |
| Energy | XOM, CVX | 0.03 | 0.28 | Moderate-high |
| Industrial | CAT, GE, UPS, HD, LMT | 0.04 | 0.22 | Moderate |

### Complete Implementation

```python
# backend/market/simulator.py

"""GBM-based market simulator with jump events and soft mean reversion.

Generates realistic price movements using geometric Brownian motion (GBM):
    S(t+dt) = S(t) × exp((μ - σ²/2) × dt + σ × √dt × Z)

Features:
- Per-ticker drift and volatility reflecting real-world character
- Merton jump-diffusion: occasional sudden 2-5% moves for visual drama
- Soft mean reversion: prevents prices drifting too far from seed
- Runs as an asyncio background task, updating all tickers every 500ms
- Zero external dependencies (stdlib math + random only)
"""

import asyncio
import math
import random
from dataclasses import dataclass

from .cache import PriceCache
from .tickers import SUPPORTED_TICKERS

# Time constants
SECONDS_PER_YEAR = 252 * 6.5 * 3600  # 5,896,800 — one trading year in seconds
UPDATE_INTERVAL = 0.5  # seconds between price ticks

# GBM parameters
REVERSION_SPEED = 0.1  # annualized mean-reversion rate (κ)
JUMP_INTENSITY = 0.0002  # probability of a jump event per tick per ticker
JUMP_STD = 0.03  # std dev of jump magnitude in log-space (~1-5% per event)
MIN_PRICE = 1.0  # absolute price floor ($1)
MAX_SEED_RATIO = 3.0  # hard ceiling: price cannot exceed seed × this


@dataclass(slots=True)
class TickerConfig:
    """Per-ticker simulation parameters."""

    ticker: str
    seed_price: float
    drift: float  # annualized μ (expected return)
    volatility: float  # annualized σ


class MarketSimulator:
    """GBM-based market price simulator with jump events and mean reversion.

    Usage:
        cache = PriceCache()
        sim = MarketSimulator(cache)
        await sim.start()   # initializes prices and starts background loop
        ...
        await sim.stop()    # cancels background loop
    """

    def __init__(self, cache: PriceCache) -> None:
        self._cache = cache
        self._configs = self._build_configs()
        self._current_prices: dict[str, float] = {}
        self._task: asyncio.Task | None = None

        # Precompute time-step values (constant across all ticks)
        self._dt = UPDATE_INTERVAL / SECONDS_PER_YEAR
        self._sqrt_dt = math.sqrt(self._dt)

    def _build_configs(self) -> dict[str, TickerConfig]:
        """Build per-ticker configs from the supported ticker universe."""
        configs: dict[str, TickerConfig] = {}
        for ticker, seed_price in SUPPORTED_TICKERS.items():
            drift, vol = _assign_params(ticker)
            configs[ticker] = TickerConfig(
                ticker=ticker,
                seed_price=seed_price,
                drift=drift,
                volatility=vol,
            )
        return configs

    async def start(self, initial_prices: dict[str, float] | None = None) -> None:
        """Initialize prices and start the background update loop.

        Args:
            initial_prices: Optional mapping of ticker -> price to seed from
                (e.g. last known prices from DB). Tickers not present fall back
                to their seed price from SUPPORTED_TICKERS.
        """
        for ticker, cfg in self._configs.items():
            price = (initial_prices or {}).get(ticker) or cfg.seed_price
            self._current_prices[ticker] = price
            self._cache.update(ticker, price)
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        """Cancel the background update loop and wait for it to finish."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    def get_supported_tickers(self) -> list[str]:
        """Return all tickers this simulator generates prices for."""
        return list(self._configs.keys())

    async def _run(self) -> None:
        """Main loop: advance all tickers every UPDATE_INTERVAL seconds."""
        while True:
            self._tick()
            await asyncio.sleep(UPDATE_INTERVAL)

    def _tick(self) -> None:
        """Advance all tickers by one GBM time step."""
        for ticker, cfg in self._configs.items():
            price = self._current_prices[ticker]
            new_price = self._step(price, cfg)
            self._current_prices[ticker] = new_price
            self._cache.update(ticker, new_price)

    def _step(self, price: float, cfg: TickerConfig) -> float:
        """Compute next price: GBM core + mean reversion + optional jump event.

        Uses exact discrete GBM formula (not Euler approximation):
            S(t+dt) = S(t) × exp((μ_adj - σ²/2) × dt + σ × √dt × Z)

        Mean reversion adjusts drift based on log-distance from seed:
            μ_adj = μ - κ × ln(S / S₀)
        """
        # Soft mean reversion: pull drift toward seed
        log_ratio = math.log(price / cfg.seed_price)
        adjusted_drift = cfg.drift - REVERSION_SPEED * log_ratio

        # GBM core (exact discrete, Itô-corrected)
        z = random.gauss(0.0, 1.0)
        drift_term = (adjusted_drift - 0.5 * cfg.volatility**2) * self._dt
        diffusion_term = cfg.volatility * self._sqrt_dt * z

        # Merton jump-diffusion: Poisson-distributed jumps
        jump_term = 0.0
        if random.random() < JUMP_INTENSITY:
            jump_term = random.gauss(0.0, JUMP_STD)

        new_price = price * math.exp(drift_term + diffusion_term + jump_term)

        # Hard clamp: stay within [MIN_PRICE, seed × MAX_SEED_RATIO]
        new_price = max(MIN_PRICE, min(new_price, cfg.seed_price * MAX_SEED_RATIO))

        return new_price

    @property
    def current_prices(self) -> dict[str, float]:
        """Read-only snapshot of current simulator prices (for testing)."""
        return dict(self._current_prices)


def _assign_params(ticker: str) -> tuple[float, float]:
    """Assign (drift, volatility) based on ticker's market character.

    Returns:
        (drift, volatility) as annualized floats.
    """
    # High-volatility growth/momentum
    if ticker in {"TSLA", "NVDA", "AMD", "SHOP", "SQ"}:
        return (0.04, 0.50)
    # Medium-high volatility
    if ticker in {"META", "NFLX", "AMZN", "ADBE", "CRM", "UBER", "BA", "DIS", "PYPL"}:
        return (0.05, 0.32)
    # Medium volatility (large-cap tech)
    if ticker in {"AAPL", "GOOGL", "MSFT", "ORCL", "QCOM", "AVGO", "INTC", "CSCO"}:
        return (0.05, 0.25)
    # Financial sector
    if ticker in {"JPM", "BAC", "GS", "MS", "AXP", "BLK"}:
        return (0.04, 0.22)
    # Payments (low vol)
    if ticker in {"V", "MA"}:
        return (0.04, 0.18)
    # Healthcare
    if ticker in {"JNJ", "PFE", "UNH", "MRK", "ABBV", "LLY"}:
        return (0.03, 0.22)
    # Consumer defensive (low vol)
    if ticker in {"KO", "PEP", "WMT", "COST", "MCD", "NKE", "SBUX"}:
        return (0.03, 0.18)
    # Energy
    if ticker in {"XOM", "CVX"}:
        return (0.03, 0.28)
    # Industrial
    if ticker in {"CAT", "GE", "UPS", "HD", "LMT"}:
        return (0.04, 0.22)
    # Default fallback
    return (0.04, 0.25)
```

### Restart Resilience

On restart, the simulator should seed from the last known prices in the database to avoid P&L discontinuities against stored `avg_cost` values. The `start()` method accepts an `initial_prices` dict for this purpose.

The calling code in the FastAPI lifespan should query the most recent trade price for each ticker:

```python
# In FastAPI lifespan (backend/main.py)
async def get_last_known_prices(db) -> dict[str, float]:
    """Query the most recent trade price for each ticker from the trades table."""
    rows = await db.execute("""
        SELECT ticker, price FROM trades
        WHERE (ticker, executed_at) IN (
            SELECT ticker, MAX(executed_at) FROM trades GROUP BY ticker
        )
    """)
    return {row["ticker"]: row["price"] for row in rows}

# Then at startup:
initial_prices = await get_last_known_prices(db)
await provider.start(initial_prices=initial_prices)
```

### Visual Behavior Summary

| Ticker Type | Example | What the User Sees |
|------------|---------|-------------------|
| High-vol | TSLA, NVDA | Frequent green/red flashes, noticeable dollar moves |
| Medium-vol | AAPL, GOOGL | Steady small changes, occasional larger moves |
| Low-vol | KO, V | Gentle, slow price drift — the "boring" stocks |
| Jump event | Any ticker | Sudden 2-5% spike or drop, ~1 every 100s across all tickers |

---

## 7. Module: `massive.py` — MassivePoller (REST API)

The Massive (formerly Polygon.io) poller is the alternative market data provider, used when `MASSIVE_API_KEY` is set. It polls the Massive REST API snapshot endpoint on a configurable interval.

### API Reference (Key Endpoint)

**Snapshot — Multiple Tickers:**

```
GET /v2/snapshot/locale/us/markets/stocks/tickers?tickers=AAPL,GOOGL,MSFT
Authorization: Bearer YOUR_API_KEY
```

**Response structure:**

```json
{
  "count": 3,
  "status": "OK",
  "tickers": [
    {
      "ticker": "AAPL",
      "lastTrade": { "p": 191.24, "s": 100, "t": 1702483260000 },
      "day": { "o": 189.33, "h": 191.56, "l": 188.90, "c": 191.24, "v": 54032150 },
      "prevDay": { "c": 189.33 },
      "todaysChange": 1.91,
      "todaysChangePerc": 1.009
    }
  ]
}
```

**Price extraction priority:** `lastTrade.p` → `day.c` → `prevDay.c` → `None`

### Rate Limits

| Tier | Limit | Recommended Poll Interval |
|------|-------|--------------------------|
| Free | 5 req/min | 15 seconds |
| Paid | Unlimited (stay under 100 req/sec) | 2-5 seconds |

### Complete Implementation

```python
# backend/market/massive.py

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
        ticker list. Extracts lastTrade.p as the current price for each ticker.
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
```

### Error Handling Strategy

The poll loop uses three-level exception handling to ensure it **never crashes**:

1. `httpx.HTTPStatusError` — API returned 4xx/5xx (rate limit, auth failure, etc.)
2. `httpx.RequestError` — network-level failure (DNS, timeout, connection refused)
3. `Exception` — catch-all for unexpected errors (malformed JSON, etc.)

In all cases: log the error, sleep for the poll interval, and try again. The cache retains the last known prices until new data arrives.

### Why Direct httpx Instead of the Official Client

1. Better integration with FastAPI's async architecture
2. No extra dependency to manage
3. Full control over request timing and retry logic
4. We only use 1 endpoint (snapshot)

---

## 8. Module: `__init__.py` — Factory & Public API

### Complete Implementation

```python
# backend/market/__init__.py

"""Market data package — factory function and public re-exports.

Usage in FastAPI lifespan:
    from market import create_market_provider
    from market.cache import PriceCache

    cache = PriceCache()
    provider = create_market_provider(cache)

    @asynccontextmanager
    async def lifespan(app):
        await provider.start()
        yield
        await provider.stop()
"""

import os

from .cache import PriceCache
from .massive import MassivePoller
from .simulator import MarketSimulator


def create_market_provider(cache: PriceCache) -> MarketSimulator | MassivePoller:
    """Select and instantiate the appropriate market data provider.

    Uses MassivePoller if MASSIVE_API_KEY env var is set and non-empty,
    otherwise falls back to the built-in MarketSimulator.
    """
    api_key = os.environ.get("MASSIVE_API_KEY", "").strip()

    if api_key:
        return MassivePoller(cache=cache, api_key=api_key)
    else:
        return MarketSimulator(cache=cache)


__all__ = [
    "create_market_provider",
    "PriceCache",
    "MarketSimulator",
    "MassivePoller",
]
```

### Selection Logic

| `MASSIVE_API_KEY` value | Provider selected |
|------------------------|-------------------|
| Not set | `MarketSimulator` |
| Empty string `""` | `MarketSimulator` |
| Whitespace only `"   "` | `MarketSimulator` |
| Any non-empty string | `MassivePoller` |

The `.strip()` call handles accidental whitespace in `.env` files.

---

## 9. Integration with FastAPI

### Lifespan Setup

```python
# backend/main.py (relevant excerpt)

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from market import create_market_provider
from market.cache import PriceCache

# Create shared instances at module level
price_cache = PriceCache()
provider = create_market_provider(price_cache)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: begin generating/fetching prices
    # Optional: load last known prices from DB for restart resilience
    # initial_prices = await get_last_known_prices(db)
    # await provider.start(initial_prices=initial_prices)
    await provider.start()
    yield
    # Shutdown: clean up background tasks
    await provider.stop()


app = FastAPI(lifespan=lifespan)

# Mount API routes
# app.include_router(stream_router, prefix="/api/stream")
# app.include_router(portfolio_router, prefix="/api/portfolio")
# app.include_router(watchlist_router, prefix="/api/watchlist")
# app.include_router(chat_router, prefix="/api")

# Serve frontend static files (must be last — catch-all)
# app.mount("/", StaticFiles(directory="static", html=True), name="static")
```

### Accessing PriceCache from Route Handlers

The `price_cache` is a module-level singleton. Route handlers import it directly:

```python
# backend/routes/stream.py
from main import price_cache

# Or use FastAPI's app.state:
app.state.price_cache = price_cache

# Then in route handlers:
@router.get("/api/stream/prices")
async def stream_prices(request: Request):
    cache = request.app.state.price_cache
    ...
```

Either approach works. Module-level import is simpler; `app.state` is more explicit about dependencies.

---

## 10. SSE Streaming Consumer

The SSE endpoint reads from PriceCache on a fixed cadence and pushes updates to connected browser clients. It uses `sse-starlette` for the SSE protocol.

### Implementation

```python
# backend/routes/stream.py

import asyncio
import json

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

router = APIRouter()


@router.get("/api/stream/prices")
async def stream_prices(request: Request):
    """SSE endpoint: pushes price updates for the user's watchlist tickers."""
    price_cache = request.app.state.price_cache

    async def generate():
        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                break

            # Get current watchlist from DB
            watchlist_tickers = await get_user_watchlist()  # returns list[str]

            # Read latest prices for watchlist tickers
            prices = price_cache.get_many(watchlist_tickers)

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

            await asyncio.sleep(0.5)  # Match simulator update interval

    return EventSourceResponse(generate())
```

### SSE Event Format

Each event sent to the client:

```
event: price
data: {"ticker":"AAPL","price":191.24,"previousPrice":190.50,"timestamp":1702483260.123,"direction":"up"}

event: price
data: {"ticker":"TSLA","price":251.30,"previousPrice":252.10,"timestamp":1702483260.123,"direction":"down"}
```

### Frontend EventSource Usage

```typescript
const source = new EventSource('/api/stream/prices');

source.addEventListener('price', (event) => {
  const data = JSON.parse(event.data);
  // data = { ticker, price, previousPrice, timestamp, direction }
  updateWatchlistPrice(data);
});

source.onerror = () => {
  // EventSource automatically reconnects with exponential backoff
  updateConnectionStatus('reconnecting');
};
```

### Key Design Points

- The SSE endpoint queries the watchlist on every iteration (every 500ms). This means watchlist changes are reflected in the stream within 500ms without reconnecting.
- `request.is_disconnected()` check prevents the server from generating events for closed connections.
- The 500ms sleep matches the simulator's update interval. For the Massive poller (15s updates), the SSE stream will push the same cached data repeatedly — this is fine because the frontend only flashes on price *changes* (direction != flat).

---

## 11. Trade Execution Consumer

Trade execution reads the current price from the cache at the moment of the trade.

### Implementation

```python
# backend/routes/portfolio.py (trade execution excerpt)

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from market.tickers import SUPPORTED_TICKERS

router = APIRouter()


class TradeRequest(BaseModel):
    ticker: str
    quantity: float
    side: str  # "buy" or "sell"


@router.post("/api/portfolio/trade")
async def execute_trade(req: TradeRequest, request: Request):
    price_cache = request.app.state.price_cache

    # Validate ticker is in supported universe
    if req.ticker not in SUPPORTED_TICKERS:
        raise HTTPException(400, detail={
            "error": f"Ticker {req.ticker} is not supported",
            "code": "INVALID_TICKER",
        })

    # Validate minimum quantity
    if req.quantity < 0.001:
        raise HTTPException(400, detail={
            "error": "Minimum trade quantity is 0.001",
            "code": "BELOW_MINIMUM_QUANTITY",
        })

    # Get current price from cache
    current_price = price_cache.get_price(req.ticker)
    if current_price is None:
        raise HTTPException(400, detail={
            "error": f"No price available for {req.ticker}",
            "code": "INVALID_TICKER",
        })

    # Execute at current cache price (market order, instant fill)
    total_cost = current_price * req.quantity

    if req.side == "buy":
        # Check sufficient cash
        user = await get_user_profile()
        if user.cash_balance < total_cost:
            raise HTTPException(400, detail={
                "error": f"Insufficient cash. Need ${total_cost:.2f}, have ${user.cash_balance:.2f}",
                "code": "INSUFFICIENT_CASH",
            })
        # Deduct cash, update/create position, record trade
        ...

    elif req.side == "sell":
        # Check sufficient shares
        position = await get_position(req.ticker)
        if not position or position.quantity < req.quantity:
            raise HTTPException(400, detail={
                "error": f"Insufficient shares of {req.ticker}",
                "code": "INSUFFICIENT_SHARES",
            })
        # Add cash, update/remove position, record trade
        ...
```

The price cache is the bridge between market data and trade execution — the trade happens at whatever price the cache currently holds.

---

## 12. Testing Strategy

### Test Structure

```
backend/tests/market/
  __init__.py
  test_cache.py       # 22 tests — PriceCache and TickerPrice
  test_simulator.py   # 29 tests — GBM math, lifecycle, ticking
  test_massive.py     # 33 tests — parsing, polling, error handling
  test_provider.py    #  7 tests — factory function, protocol conformance
```

### Key Test Categories

#### PriceCache Tests (test_cache.py)

```python
# Direction logic
def test_first_update_has_flat_direction():
    cache = PriceCache()
    entry = cache.update("AAPL", 190.0)
    assert entry.direction == "flat"
    assert entry.previous_price == 190.0

def test_price_increase_sets_direction_up():
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    entry = cache.update("AAPL", 191.0)
    assert entry.direction == "up"
    assert entry.previous_price == 190.0

# Rounding
def test_price_is_rounded_to_2_decimals():
    cache = PriceCache()
    entry = cache.update("AAPL", 190.12345)
    assert entry.price == 190.12

# get_many skips missing tickers
def test_get_many_skips_missing_tickers():
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    entries = cache.get_many(["AAPL", "ZZZZ"])
    assert len(entries) == 1
```

#### Simulator Tests (test_simulator.py)

```python
# GBM math verification (mock randomness to get deterministic result)
def test_step_gbm_math_without_jumps():
    cache = PriceCache()
    sim = MarketSimulator(cache)
    cfg = TickerConfig(ticker="AAPL", seed_price=100.0, drift=0.05, volatility=0.25)

    # Mock: Z=0 (no random movement), no jump
    random.gauss = lambda mu, sigma: 0.0
    random.random = lambda: 1.0  # > JUMP_INTENSITY, so no jump

    new_price = sim._step(100.0, cfg)

    # Expected: only drift applies (at seed, mean reversion = 0)
    dt = sim._dt
    expected = 100.0 * math.exp((0.05 - 0.5 * 0.25**2) * dt)
    assert abs(new_price - expected) < 1e-10

# Mean reversion direction
def test_mean_reversion_pulls_down_above_seed():
    # When price > seed, adjusted drift < base drift
    log_ratio = math.log(200.0 / 100.0)
    adjusted = 0.05 - 0.1 * log_ratio
    assert adjusted < 0.05

# Price bounds
def test_step_respects_min_price_floor():
    cache = PriceCache()
    sim = MarketSimulator(cache)
    cfg = TickerConfig(ticker="X", seed_price=1.0, drift=0.0, volatility=0.5)
    for _ in range(200):
        price = sim._step(MIN_PRICE, cfg)
        assert price >= MIN_PRICE

# Lifecycle
async def test_start_populates_cache():
    cache = PriceCache()
    sim = MarketSimulator(cache)
    await sim.start()
    try:
        for ticker in SUPPORTED_TICKERS:
            assert cache.get(ticker) is not None
    finally:
        await sim.stop()

# Custom initial prices (restart resilience)
async def test_start_with_custom_initial_prices():
    cache = PriceCache()
    sim = MarketSimulator(cache)
    await sim.start(initial_prices={"AAPL": 200.0, "TSLA": 300.0})
    try:
        assert sim.current_prices["AAPL"] == 200.0
        assert sim.current_prices["TSLA"] == 300.0
        assert sim.current_prices["GOOGL"] == SUPPORTED_TICKERS["GOOGL"]
    finally:
        await sim.stop()
```

#### Massive Poller Tests (test_massive.py)

```python
# Price extraction fallback chain
def test_prefers_last_trade_price():
    data = {"ticker": "AAPL", "lastTrade": {"p": 191.0}, "day": {"c": 192.0}}
    assert _extract_price(data) == 191.0

def test_falls_back_to_day_close():
    data = {"ticker": "AAPL", "day": {"c": 192.0}, "prevDay": {"c": 189.0}}
    assert _extract_price(data) == 192.0

def test_returns_none_when_no_price():
    assert _extract_price({"ticker": "AAPL"}) is None

# Snapshot parsing
def test_skips_unsupported_tickers():
    poller = MassivePoller(cache=PriceCache(), api_key="test")
    data = {"tickers": [
        {"ticker": "AAPL", "lastTrade": {"p": 191.0}},
        {"ticker": "ZZZZ", "lastTrade": {"p": 50.0}},
    ]}
    result = poller.parse_snapshot_response(data)
    assert "AAPL" in result
    assert "ZZZZ" not in result

# Error resilience (poll loop doesn't crash)
async def test_continues_after_http_error():
    cache = PriceCache()
    poller = MassivePoller(cache=cache, api_key="test", poll_interval=0.05)
    call_count = 0

    async def flaky_fetch():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            mock_resp = MagicMock(status_code=429, text="Rate limited")
            raise httpx.HTTPStatusError("rate limited", request=MagicMock(), response=mock_resp)

    with patch.object(poller, "_fetch_and_update", side_effect=flaky_fetch):
        poller._client = MagicMock()
        poller._task = asyncio.create_task(poller._poll_loop())
        await asyncio.sleep(0.2)
        poller._task.cancel()

    assert call_count >= 3  # Survived errors and kept polling
```

#### Factory Tests (test_provider.py)

```python
def test_returns_simulator_when_no_api_key():
    cache = PriceCache()
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("MASSIVE_API_KEY", None)
        provider = create_market_provider(cache)
    assert isinstance(provider, MarketSimulator)

def test_returns_massive_when_api_key_set():
    cache = PriceCache()
    with patch.dict(os.environ, {"MASSIVE_API_KEY": "real-key"}):
        provider = create_market_provider(cache)
    assert isinstance(provider, MassivePoller)

def test_whitespace_only_key_uses_simulator():
    cache = PriceCache()
    with patch.dict(os.environ, {"MASSIVE_API_KEY": "   "}):
        provider = create_market_provider(cache)
    assert isinstance(provider, MarketSimulator)
```

### Running Tests

```bash
cd backend
uv run pytest tests/market/ -v
```

Expected: **91 tests, all passing** in ~1.5 seconds.

---

## 13. Dependencies

### Runtime (in `pyproject.toml`)

| Package | Version | Used By |
|---------|---------|---------|
| `httpx` | >=0.27.0 | `MassivePoller` — async HTTP client |
| `sse-starlette` | >=2.1.0 | SSE streaming endpoint |
| `fastapi` | >=0.115.0 | App framework, lifespan |
| `uvicorn[standard]` | >=0.30.0 | ASGI server |

The `MarketSimulator` has **zero external dependencies** — it uses only `math`, `random`, and `asyncio` from the standard library.

### Dev (test) Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `pytest` | >=8.0.0 | Test runner |
| `pytest-asyncio` | >=0.23.0 | Async test support |

### pyproject.toml Config

```toml
[project]
name = "finally-backend"
version = "0.1.0"
description = "FinAlly trading workstation backend"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "sse-starlette>=2.1.0",
    "httpx>=0.27.0",
    "litellm>=1.40.0",
    "pydantic>=2.7.0",
    "python-dotenv>=1.0.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["market"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[dependency-groups]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
]
```
