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
