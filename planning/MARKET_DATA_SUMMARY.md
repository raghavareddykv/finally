# Market Data Backend — Complete Reference

This is the single consolidated document for the FinAlly market data subsystem. It covers architecture, implementation details, API integration, testing, and code review findings.

---

## Architecture

```
MarketSimulator (GBM, 500ms)  ──┐
        OR                      ├──▶ PriceCache ◀── SSE / Trade Execution / Portfolio / LLM
MassivePoller (REST, 15s)    ──┘
        writes only                    reads only
```

**Design principles:**
- **Provider writes, consumers read** — unidirectional data flow
- **Protocol-based polymorphism** — `MarketDataProvider` uses `typing.Protocol` (structural typing, no inheritance)
- **Factory pattern** — `create_market_provider(cache)` selects provider based on `MASSIVE_API_KEY` env var
- **Single PriceCache dict** — safe for asyncio cooperative scheduling (no locks needed)

---

## File Layout

```
backend/market/
  __init__.py       # create_market_provider() factory + public re-exports
  cache.py          # PriceCache + TickerPrice dataclass
  provider.py       # MarketDataProvider Protocol
  tickers.py        # SUPPORTED_TICKERS dict (48 tickers, 6 sectors)
  simulator.py      # MarketSimulator — GBM with jumps and mean reversion
  massive.py        # MassivePoller — Massive (Polygon.io) REST API client
```

---

## Supported Tickers (48 total)

| Sector | Tickers | Count |
|--------|---------|-------|
| Tech | AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, NFLX, AMD, INTC, CRM, ORCL, ADBE, CSCO, QCOM, AVGO, UBER, SQ, SHOP, PYPL | 20 |
| Finance | JPM, V, MA, BAC, GS, MS, BLK, AXP | 8 |
| Healthcare | JNJ, PFE, UNH, MRK, ABBV, LLY | 6 |
| Consumer | KO, PEP, WMT, COST, MCD, NKE, SBUX, DIS | 8 |
| Industrial | BA, CAT, GE, UPS, HD, LMT | 6 |
| Energy | XOM, CVX | 2 |

Defined in `tickers.py` with realistic seed prices (e.g., AAPL=$190, NVDA=$880). This dict is the single source of truth for ticker validation across the entire app.

---

## PriceCache

- `TickerPrice` dataclass (`slots=True`): stores `ticker`, `price`, `previous_price`, `timestamp`, `direction` ("up"/"down"/"flat")
- `update(ticker, new_price)` — computes direction, rounds to 2 decimals, stores entry
- `get(ticker)` / `get_many(tickers)` / `get_price(ticker)` / `all_tickers()` — read methods
- First update for any ticker yields `direction="flat"` (previous_price = new_price)

---

## MarketSimulator (Default Provider)

Generates prices using **Geometric Brownian Motion (GBM)** with exact discrete formula:

```
S(t+dt) = S(t) * exp((mu_adj - sigma^2/2) * dt + sigma * sqrt(dt) * Z)
```

### Key Features

| Feature | Details |
|---------|---------|
| Update frequency | Every 500ms |
| Time step | dt = 0.5 / 5,896,800 (trading seconds/year) |
| Per-ticker volatility | 0.18 (defensive) to 0.50 (growth) annualized |
| Per-ticker drift | 0.03 to 0.05 annualized |
| Mean reversion | `mu_adj = mu - 0.1 * ln(S/S0)` — soft pull toward seed price |
| Jump events | Poisson, lambda=0.0002/tick — ~1 jump per 100s across all tickers, 2-5% magnitude |
| Price bounds | Floor: $1.00, Ceiling: 3x seed price |
| Dependencies | Zero (stdlib `math` + `random` only) |
| Restart resilience | `start(initial_prices=...)` accepts last known prices from DB |

### Volatility Tiers

| Category | Tickers | Drift | Volatility |
|----------|---------|-------|------------|
| High-vol growth | TSLA, NVDA, AMD, SHOP, SQ | 0.04 | 0.50 |
| Med-high vol | META, NFLX, AMZN, ADBE, CRM, UBER, BA, DIS, PYPL | 0.05 | 0.32 |
| Large-cap tech | AAPL, GOOGL, MSFT, ORCL, QCOM, AVGO, INTC, CSCO | 0.05 | 0.25 |
| Financial | JPM, BAC, GS, MS, AXP, BLK | 0.04 | 0.22 |
| Payments | V, MA | 0.04 | 0.18 |
| Healthcare | JNJ, PFE, UNH, MRK, ABBV, LLY | 0.03 | 0.22 |
| Consumer defensive | KO, PEP, WMT, COST, MCD, NKE, SBUX | 0.03 | 0.18 |
| Energy | XOM, CVX | 0.03 | 0.28 |
| Industrial | CAT, GE, UPS, HD, LMT | 0.04 | 0.22 |

---

## MassivePoller (Optional Provider)

Used when `MASSIVE_API_KEY` is set. Polls Massive (formerly Polygon.io) REST API.

### API Details

- **Endpoint:** `GET /v2/snapshot/locale/us/markets/stocks/tickers?tickers=AAPL,GOOGL,...`
- **Auth:** `Authorization: Bearer {api_key}`
- **Price extraction fallback:** `lastTrade.p` -> `day.c` -> `prevDay.c` -> `None`
- **Rate limits:** Free tier = 5 req/min (poll every 15s), Paid = unlimited (poll every 2-5s)
- **Error handling:** Three-level catch (`HTTPStatusError`, `RequestError`, `Exception`) — loop never crashes

### Why httpx over official client

1. Better async integration with FastAPI
2. No extra dependency
3. Full control over timing/retry
4. Only 1 endpoint needed

---

## Factory Function

```python
create_market_provider(cache: PriceCache) -> MarketSimulator | MassivePoller
```

| `MASSIVE_API_KEY` | Provider |
|-------------------|----------|
| Not set / empty / whitespace | `MarketSimulator` |
| Any non-empty string | `MassivePoller` |

---

## FastAPI Integration

```python
from market import create_market_provider
from market.cache import PriceCache

cache = PriceCache()
provider = create_market_provider(cache)

@asynccontextmanager
async def lifespan(app):
    await provider.start()  # or provider.start(initial_prices=...)
    yield
    await provider.stop()
```

SSE endpoint reads from `PriceCache.get_many(watchlist)` every 500ms.
Trade execution reads from `PriceCache.get_price(ticker)` at trade time.

---

## Test Results

**91 tests, all passing** (1.42s)

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `test_cache.py` | 22 | Direction logic, rounding, get_many edge cases |
| `test_simulator.py` | 29 | GBM math, mean reversion, jumps, bounds, lifecycle |
| `test_massive.py` | 33 | Price extraction, parsing, error resilience |
| `test_provider.py` | 7 | Factory selection, protocol conformance |

### Running Tests

```bash
cd backend && uv run pytest tests/market/ -v
```

---

## Code Review Findings (2026-03-20)

**Verdict: Ready to build on.**

### Strengths
- GBM math is correct (Ito-corrected exact discrete formula)
- Clean protocol-based architecture
- Comprehensive test suite with mocked randomness for deterministic verification
- Error-resilient polling loop in MassivePoller

### Minor Notes (Non-blocking)
- Direction comparison happens before rounding (theoretical micro-flicker, harmless)
- `assert` in `MassivePoller._fetch_and_update` could be a guard clause
- `respx` dev dependency declared but unused (tests use `unittest.mock`)
- No guard against double `start()` calls

---

## Dependencies

### Runtime
| Package | Used By |
|---------|---------|
| `httpx >=0.27.0` | MassivePoller |
| `sse-starlette >=2.1.0` | SSE streaming |
| `fastapi >=0.115.0` | App framework |
| `uvicorn[standard] >=0.30.0` | ASGI server |

### Dev
| Package | Purpose |
|---------|---------|
| `pytest >=8.0.0` | Test runner |
| `pytest-asyncio >=0.23.0` | Async test support |

MarketSimulator has **zero external dependencies** — stdlib only.

---

## Demo

See `planning/market_data_demo.py` for a runnable demo that starts the simulator, streams prices for a watchlist, and displays live updates in the terminal.
