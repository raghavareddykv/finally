# Market Simulator Design

The simulator generates realistic stock price movements using **geometric Brownian motion (GBM)** with jump events and soft mean reversion. It runs as an asyncio background task, updating all tickers every 500ms and writing to the shared `PriceCache`.

## Mathematical Model

### Core GBM Equation (Discrete-Time, Exact)

```
S(t + dt) = S(t) × exp((μ - σ²/2) × dt + σ × √dt × Z)
```

Where:
- **S(t)** = current price
- **μ** (mu) = annualized drift (expected return, e.g. 0.05 = 5%/year)
- **σ** (sigma) = annualized volatility (e.g. 0.25 = 25%/year)
- **dt** = time step as a fraction of a year
- **Z** ~ N(0, 1) = standard normal random draw

The exponential form guarantees prices stay positive — no clamping needed for negativity.

The `- σ²/2` correction (Itô's lemma) ensures the expected return equals μ, not μ + σ²/2.

### Time Step Calculation

Trading year = 252 days × 6.5 hours/day = 5,896,800 seconds.

For 500ms ticks:

```python
SECONDS_PER_YEAR = 252 * 6.5 * 3600  # 5,896,800
UPDATE_INTERVAL = 0.5                  # seconds
dt = UPDATE_INTERVAL / SECONDS_PER_YEAR  # ≈ 8.478e-8
sqrt_dt = math.sqrt(dt)                  # ≈ 2.912e-4
```

With this tiny dt, each tick produces ~0.01–0.05% price change for typical volatilities — realistic.

### Jump Events (Merton Jump-Diffusion)

Occasional sudden moves (2–5%) for visual drama. Modeled as a Poisson process:

```
On each tick, with probability λ:
    jump = N(0, jump_σ)  where jump_σ ≈ 0.03
```

| Parameter | Value | Effect |
|-----------|-------|--------|
| `jump_intensity` (λ) | 0.0002 per tick | ~1 jump per 83 min per ticker; ~1 jump per 100s across 50 tickers |
| `jump_mean` | 0.0 | Jumps equally likely up or down |
| `jump_std` | 0.03 | Most jumps are 1–5% (within 2σ) |

### Soft Mean Reversion

Prevents prices from drifting too far from their seed over long sessions. Applied in log-space:

```
adjusted_μ = μ - κ × ln(S / S₀)
```

Where **κ** = reversion speed (annualized, e.g. 0.1) and **S₀** = seed price.

When price > seed: drift decreases (pulled back down).
When price < seed: drift increases (pulled back up).

With κ = 0.1, prices can wander ±20–30% from seed but slowly drift back over hours.

---

## Per-Ticker Parameters

Each ticker has its own volatility and drift, reflecting its real-world character.

```python
# Volatility tiers
LOW_VOL = 0.18     # Defensive: KO, V, JNJ, PEP
MED_VOL = 0.28     # Large-cap tech: AAPL, MSFT, GOOGL
HIGH_VOL = 0.45    # Growth/momentum: TSLA, NVDA, AMD

# Drift: modest across the board (barely noticeable in a demo session)
LOW_DRIFT = 0.03
MED_DRIFT = 0.05
HIGH_DRIFT = 0.07
```

Example configuration (full list in `tickers.py`):

| Ticker | Seed Price | Drift | Volatility | Character |
|--------|-----------|-------|------------|-----------|
| AAPL | $190 | 0.05 | 0.25 | Large-cap tech |
| TSLA | $250 | 0.03 | 0.55 | High-vol growth |
| KO | $60 | 0.03 | 0.15 | Defensive |
| NVDA | $880 | 0.08 | 0.45 | High-vol momentum |
| JPM | $195 | 0.04 | 0.20 | Financial, moderate |
| V | $280 | 0.04 | 0.18 | Payments, low vol |

---

## Code Structure

### TickerConfig Dataclass

```python
# backend/market/simulator.py

from dataclasses import dataclass

@dataclass(slots=True)
class TickerConfig:
    ticker: str
    seed_price: float
    drift: float       # annualized μ
    volatility: float  # annualized σ
```

### MarketSimulator Class

```python
import asyncio
import math
import random
import time
from .cache import PriceCache
from .tickers import SUPPORTED_TICKERS


# Time constants
SECONDS_PER_YEAR = 252 * 6.5 * 3600  # ~5,896,800
UPDATE_INTERVAL = 0.5  # seconds

# GBM parameters
REVERSION_SPEED = 0.1  # annualized mean-reversion rate
JUMP_INTENSITY = 0.0002  # probability of jump per tick per ticker
JUMP_STD = 0.03  # std dev of jump magnitude (log-space)
MIN_PRICE = 1.0  # absolute price floor
MAX_SEED_RATIO = 3.0  # max price = seed × this ratio


class MarketSimulator:
    """GBM-based market price simulator with jump events and mean reversion."""

    def __init__(self, cache: PriceCache) -> None:
        self._cache = cache
        self._configs = self._build_configs()
        self._current_prices: dict[str, float] = {}
        self._task: asyncio.Task | None = None

        # Precompute time-step values
        self._dt = UPDATE_INTERVAL / SECONDS_PER_YEAR
        self._sqrt_dt = math.sqrt(self._dt)

    def _build_configs(self) -> dict[str, TickerConfig]:
        """Build per-ticker configs from the supported ticker universe."""
        configs = {}
        for ticker, seed_price in SUPPORTED_TICKERS.items():
            drift, vol = _assign_params(ticker)
            configs[ticker] = TickerConfig(
                ticker=ticker,
                seed_price=seed_price,
                drift=drift,
                volatility=vol,
            )
        return configs

    async def start(self) -> None:
        """Initialize prices and start the background update loop."""
        for ticker, cfg in self._configs.items():
            # TODO: On restart, load last known price from DB instead of seed
            self._current_prices[ticker] = cfg.seed_price
            self._cache.update(ticker, cfg.seed_price)
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        """Cancel the background task."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def get_supported_tickers(self) -> list[str]:
        return list(self._configs.keys())

    async def _run(self) -> None:
        """Main loop: update all tickers every UPDATE_INTERVAL seconds."""
        while True:
            self._tick()
            await asyncio.sleep(UPDATE_INTERVAL)

    def _tick(self) -> None:
        """Advance all tickers by one time step."""
        for ticker, cfg in self._configs.items():
            price = self._current_prices[ticker]
            new_price = self._step(price, cfg)
            self._current_prices[ticker] = new_price
            self._cache.update(ticker, new_price)

    def _step(self, price: float, cfg: TickerConfig) -> float:
        """Single GBM step with mean reversion and jump events."""
        # Soft mean reversion: adjust drift based on distance from seed
        log_ratio = math.log(price / cfg.seed_price)
        adjusted_drift = cfg.drift - REVERSION_SPEED * log_ratio

        # GBM core
        z = random.gauss(0.0, 1.0)
        drift = (adjusted_drift - 0.5 * cfg.volatility ** 2) * self._dt
        diffusion = cfg.volatility * self._sqrt_dt * z

        # Jump event (Poisson)
        jump = 0.0
        if random.random() < JUMP_INTENSITY:
            jump = random.gauss(0.0, JUMP_STD)

        new_price = price * math.exp(drift + diffusion + jump)

        # Safety clamp
        new_price = max(MIN_PRICE, min(new_price, cfg.seed_price * MAX_SEED_RATIO))

        return new_price


def _assign_params(ticker: str) -> tuple[float, float]:
    """Assign drift and volatility based on ticker character.

    Returns (drift, volatility).
    """
    # High-volatility tickers
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
    # Default
    return (0.04, 0.25)
```

---

## Restart Resilience

On restart, the simulator should seed from the **last known price** in the database (from the most recent trade or portfolio snapshot) to avoid P&L discontinuities against stored `avg_cost` values.

```python
async def start(self, db=None) -> None:
    """Initialize prices and start the background update loop."""
    for ticker, cfg in self._configs.items():
        last_price = None
        if db:
            last_price = await db.get_last_known_price(ticker)
        self._current_prices[ticker] = last_price or cfg.seed_price
        self._cache.update(ticker, self._current_prices[ticker])
    self._task = asyncio.create_task(self._run())
```

The `get_last_known_price()` query checks:
1. The most recent trade for this ticker (from the `trades` table)
2. Falls back to the seed price if no trades exist

---

## Behavior at a Glance

| Aspect | Behavior |
|--------|----------|
| Update frequency | Every 500ms |
| Price model | GBM (exact discrete, not Euler) |
| Drift | Per-ticker, 2–8% annualized — barely perceptible in a demo |
| Volatility | Per-ticker, 15–55% annualized — produces visible but realistic movement |
| Jump events | ~1 event per 100s across all 50 tickers; 2–5% magnitude |
| Mean reversion | Soft pull toward seed; prices wander ±20–30% before reverting |
| Price floor | $1.00 absolute minimum |
| Price ceiling | 3× seed price per ticker |
| Dependencies | None (stdlib `math` + `random` only) |
| Thread safety | Single asyncio event loop — no locks needed |

---

## Visual Result

With these parameters, the user sees:
- **Most tickers:** Small, frequent price changes (pennies to a few dollars) — prices gently wander
- **High-vol tickers (TSLA, NVDA):** Noticeably more movement, more frequent green/red flashes
- **Occasional jumps:** Every ~2 minutes, some ticker makes a sudden 2–5% move — catches the eye in the watchlist
- **No runaway prices:** Mean reversion keeps everything anchored near realistic levels over long sessions
