# Market Data Backend — Code Review

**Date:** 2026-03-20
**Reviewer:** Claude (AI Code Review)
**Scope:** `backend/market/` package and `backend/tests/market/` tests

---

## Test Results

**91 tests, 91 passed, 0 failed** (1.42s)

| Test File | Tests | Status |
|-----------|-------|--------|
| `test_cache.py` | 22 | All pass |
| `test_massive.py` | 33 | All pass |
| `test_provider.py` | 7 | All pass |
| `test_simulator.py` | 29 | All pass |

---

## Architecture Assessment

The market data subsystem is well-designed and faithfully implements the architecture described in `MARKET_INTERFACE.md`. Key strengths:

- **Clean separation of concerns:** Provider (writes) → PriceCache (shared state) → Consumers (reads). Downstream code never depends on a specific provider.
- **Protocol-based polymorphism:** `MarketDataProvider` uses `typing.Protocol` for structural typing — providers don't inherit from anything, keeping the code flexible.
- **Single source of truth:** `SUPPORTED_TICKERS` in `tickers.py` is used consistently across all modules for validation and initialization.
- **Factory pattern:** `create_market_provider()` in `__init__.py` cleanly selects the provider based on environment config.

---

## Module-by-Module Review

### `tickers.py` — Supported Ticker Universe

**Status: Good**

- 48 tickers across 6 sectors with realistic seed prices.
- Well-organized by sector with comments.
- Matches the PLAN.md spec of ~50 tickers.
- No issues found.

### `cache.py` — PriceCache & TickerPrice

**Status: Good**

- `TickerPrice` uses `@dataclass(slots=True)` for memory efficiency — appropriate for a high-frequency data structure.
- Direction logic (`up`/`down`/`flat`) is correct: first update is always `flat` since `previous_price` defaults to `new_price`.
- Prices are rounded to 2 decimal places — correct for USD.
- `all_tickers()` method extends beyond the spec in `MARKET_INTERFACE.md` — useful addition.
- Thread safety comment is accurate: single-process asyncio with cooperative scheduling means no locks needed.

**Minor observations:**
- The direction comparison uses the rounded `new_price` against the raw `prev.price` (which was already rounded on storage). This is fine since both values go through `round()` before storage, but the comparison at lines 33-38 happens *before* the rounding at line 41. In theory, `new_price=100.005` and `previous_price=100.00` would show `direction="up"` but `price=100.00` after rounding — a direction flicker with no visible price change. This is extremely unlikely with real price data and harmless, but worth noting.

### `simulator.py` — MarketSimulator (GBM)

**Status: Good — mathematically sound**

- **GBM implementation is correct.** Uses the exact discrete formula `S * exp((mu_adj - sigma^2/2) * dt + sigma * sqrt(dt) * Z)` with the Ito correction term `-sigma^2/2`.
- **Time step calculation is correct:** `dt = 0.5 / 5,896,800 ≈ 8.48e-8`, producing realistic sub-penny per-tick movements.
- **Mean reversion** is implemented correctly in log-space: `adjusted_drift = drift - kappa * ln(S/S0)`.
- **Jump events** use Poisson arrival with `lambda=0.0002` per tick — yields ~1 jump per 83 minutes per ticker, or about one visible jump every ~100 seconds across the full universe. Good for visual drama.
- **Safety clamps** prevent pathological prices: floor at $1, ceiling at 3x seed.
- **`_assign_params`** covers all 48 tickers with sensible sector-based volatility tiers. Every ticker in `SUPPORTED_TICKERS` matches a classification bucket — verified by `test_all_supported_tickers_have_valid_params`.
- **Restart resilience:** `start()` accepts optional `initial_prices` dict for seeding from last known DB prices, as specified in `MARKET_SIMULATOR.md`.

**Minor observations:**
- `_assign_params` uses a linear chain of `if ... in set` checks. With 48 tickers and 9 categories, this is perfectly fine for startup-only code. A dict lookup would be marginal faster but less readable.
- The `_tick()` method updates all 48 tickers synchronously in a single event loop iteration. At ~48 `math.exp()` calls, this is sub-microsecond total — no risk of blocking the event loop.

### `massive.py` — MassivePoller

**Status: Good**

- **`_extract_price` fallback chain** is well-considered: `lastTrade.p` → `day.c` → `prevDay.c` → `None`. This handles free-tier limitations gracefully.
- **Error handling in `_poll_loop`** catches `HTTPStatusError`, `RequestError`, and generic `Exception` — the loop never crashes. Errors are logged and polling continues.
- **`parse_snapshot_response`** is exposed as a public method for testability — good practice.
- **`base_url` is configurable** via constructor parameter — enables testing without mocking httpx internals.
- **Cleanup is thorough:** `stop()` cancels the task, awaits it, and closes the HTTP client. Calling `stop()` when not started is safe (idempotent).
- Uses `logging` module instead of `print()` — correct for production code.

**Minor observations:**
- The `assert self._client is not None` in `_fetch_and_update()` (line 110) will raise `AssertionError` in production if assertions aren't stripped. Since `_fetch_and_update` is only called from `_poll_loop` which runs after `start()`, this is practically unreachable. However, if Python is run with `-O` (optimize), the assert is stripped entirely. Consider replacing with a guard clause `if self._client is None: return` for defense-in-depth, though this is non-critical.
- The poller sends the entire 48-ticker universe in each request. The PLAN.md mentions potentially refining to only watched tickers. This is fine for now — one API call with a comma-separated list is efficient, and the cache naturally handles superset data.

### `__init__.py` — Factory Function

**Status: Good**

- Clean environment-variable-based selection.
- Strips whitespace from `MASSIVE_API_KEY` — handles accidental spaces in `.env` files.
- `__all__` exports are complete and correct.

### `provider.py` — MarketDataProvider Protocol

**Status: Good**

- Minimal, correct Protocol definition with `start()`, `stop()`, and `get_supported_tickers()`.
- Both `MarketSimulator` and `MassivePoller` structurally conform without inheriting from it — verified by `test_provider_conforms_to_protocol`.

---

## Test Quality Assessment

### Strengths

- **Comprehensive coverage:** All public methods and key internal methods are tested.
- **GBM math is verified:** `test_step_gbm_math_without_jumps` mocks randomness to verify the exact formula. Mean reversion direction is tested both above and below seed.
- **Edge cases covered:** Empty inputs, missing keys, zero prices, idempotent stop, whitespace-only API keys.
- **Async lifecycle tests** properly use try/finally to ensure `stop()` is always called — prevents leaked tasks.
- **Error resilience tested:** The poll loop error handling tests verify the loop survives HTTP errors and network failures.
- **Statistical tests:** `test_step_high_vol_produces_more_variance` verifies that the volatility parameter actually affects output distribution.

### Areas for Additional Testing (Non-Blocking)

These are suggestions for future improvement, not blockers:

1. **Negative price in `_extract_price`:** A test for negative `lastTrade.p` values would confirm the `price > 0` guard in `_fetch_and_update` handles this correctly.
2. **`PriceCache.update` with negative price:** The cache doesn't validate that prices are positive — it trusts the provider. This is fine given both providers enforce positive prices, but a test documenting this assumption would be useful.
3. **Concurrent `start()` calls:** What happens if `start()` is called twice without `stop()`? Currently it would overwrite `_task` without canceling the first one, leaking a background task. A guard or test would be good.
4. **`respx` unused:** The `respx` library is declared as a dev dependency but not used in any tests — `MassivePoller` tests use `unittest.mock` instead. Either use `respx` for more realistic HTTP mocking or remove the dependency.

---

## Conformance with PLAN.md

| Requirement | Status | Notes |
|---|---|---|
| Two implementations, one interface | Done | Protocol + factory pattern |
| ~50 supported tickers | Done | 48 tickers defined |
| Simulator: GBM with drift/volatility | Done | Exact discrete formula, Ito-corrected |
| Simulator: Jump events (2-5%) | Done | Poisson-distributed, sigma=0.03 |
| Simulator: Soft mean reversion | Done | Log-space, kappa=0.1 |
| Simulator: 500ms update interval | Done | `UPDATE_INTERVAL = 0.5` |
| Simulator: Seed from last known price on restart | Done | `start(initial_prices=...)` parameter |
| Simulator: Price floor $1 | Done | `MIN_PRICE = 1.0` |
| Massive: REST polling (not WebSocket) | Done | httpx GET with configurable interval |
| Massive: 15s default poll (free tier) | Done | `DEFAULT_POLL_INTERVAL = 15.0` |
| Massive: Parse `lastTrade.p` | Done | With fallback chain |
| Shared PriceCache | Done | Single cache, provider-agnostic |
| Env var driven selection | Done | `MASSIVE_API_KEY` check |
| Error handling (don't crash loop) | Done | Three-level exception handling |

---

## Build Configuration Issue

The `pyproject.toml` was missing a `[tool.hatch.build.targets.wheel]` section, causing `uv sync` to fail because hatchling couldn't find the package directory. This was fixed by adding:

```toml
[tool.hatch.build.targets.wheel]
packages = ["market"]
```

This is a build tooling issue, not a code quality issue — the market data code itself is correct.

---

## Summary

The market data backend is **well-implemented, well-tested, and closely follows both the PLAN.md specification and the detailed design documents.** The code is clean, idiomatic Python with good use of type hints, dataclasses, asyncio patterns, and the Protocol typing pattern. The GBM math is correct and the test suite is thorough with 91 passing tests.

**Verdict: Ready to build on.** The next layers (SSE streaming, trade execution, portfolio valuation) can depend on `PriceCache` with confidence.

### Action Items (Priority Order)

1. **Fix** (done): Add `[tool.hatch.build.targets.wheel]` to `pyproject.toml`
2. **Low priority:** Guard against double `start()` calls in both providers
3. **Low priority:** Replace `assert` with guard clause in `MassivePoller._fetch_and_update`
4. **Cleanup:** Remove `respx` from dev dependencies if not planning to use it, or migrate HTTP mocking to use it
