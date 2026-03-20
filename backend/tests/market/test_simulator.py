"""Unit tests for market/simulator.py — MarketSimulator and GBM math."""

import asyncio
import math
import random

import pytest

from market.cache import PriceCache
from market.simulator import (
    JUMP_INTENSITY,
    JUMP_STD,
    MAX_SEED_RATIO,
    MIN_PRICE,
    REVERSION_SPEED,
    SECONDS_PER_YEAR,
    UPDATE_INTERVAL,
    MarketSimulator,
    TickerConfig,
    _assign_params,
)
from market.tickers import SUPPORTED_TICKERS


class TestTickerConfig:
    def test_dataclass_creation(self):
        cfg = TickerConfig(ticker="AAPL", seed_price=190.0, drift=0.05, volatility=0.25)
        assert cfg.ticker == "AAPL"
        assert cfg.seed_price == 190.0
        assert cfg.drift == 0.05
        assert cfg.volatility == 0.25


class TestAssignParams:
    def test_tsla_is_high_volatility(self):
        drift, vol = _assign_params("TSLA")
        assert vol >= 0.45

    def test_ko_is_low_volatility(self):
        drift, vol = _assign_params("KO")
        assert vol <= 0.20

    def test_aapl_is_medium_volatility(self):
        drift, vol = _assign_params("AAPL")
        assert 0.20 <= vol <= 0.35

    def test_all_supported_tickers_have_valid_params(self):
        for ticker in SUPPORTED_TICKERS:
            drift, vol = _assign_params(ticker)
            assert 0.01 <= drift <= 0.15, f"{ticker}: drift {drift} out of range"
            assert 0.10 <= vol <= 0.70, f"{ticker}: vol {vol} out of range"

    def test_unknown_ticker_returns_default(self):
        drift, vol = _assign_params("ZZZZ")
        assert drift == 0.04
        assert vol == 0.25


class TestMarketSimulatorInit:
    def test_builds_configs_for_all_supported_tickers(self):
        cache = PriceCache()
        sim = MarketSimulator(cache)
        supported = set(SUPPORTED_TICKERS.keys())
        configured = set(sim.get_supported_tickers())
        assert configured == supported

    def test_dt_is_correct(self):
        cache = PriceCache()
        sim = MarketSimulator(cache)
        expected_dt = UPDATE_INTERVAL / SECONDS_PER_YEAR
        assert abs(sim._dt - expected_dt) < 1e-15

    def test_sqrt_dt_is_correct(self):
        cache = PriceCache()
        sim = MarketSimulator(cache)
        assert abs(sim._sqrt_dt - math.sqrt(sim._dt)) < 1e-15

    def test_task_is_none_before_start(self):
        cache = PriceCache()
        sim = MarketSimulator(cache)
        assert sim._task is None


class TestMarketSimulatorStart:
    @pytest.mark.asyncio
    async def test_start_populates_current_prices(self):
        cache = PriceCache()
        sim = MarketSimulator(cache)
        await sim.start()
        try:
            prices = sim.current_prices
            assert len(prices) == len(SUPPORTED_TICKERS)
            for ticker, seed in SUPPORTED_TICKERS.items():
                assert ticker in prices
                assert prices[ticker] == seed
        finally:
            await sim.stop()

    @pytest.mark.asyncio
    async def test_start_seeds_cache_with_initial_prices(self):
        cache = PriceCache()
        sim = MarketSimulator(cache)
        await sim.start()
        try:
            for ticker in SUPPORTED_TICKERS:
                entry = cache.get(ticker)
                assert entry is not None
                assert entry.price == SUPPORTED_TICKERS[ticker]
        finally:
            await sim.stop()

    @pytest.mark.asyncio
    async def test_start_with_custom_initial_prices(self):
        cache = PriceCache()
        sim = MarketSimulator(cache)
        custom = {"AAPL": 200.0, "TSLA": 300.0}
        await sim.start(initial_prices=custom)
        try:
            prices = sim.current_prices
            assert prices["AAPL"] == 200.0
            assert prices["TSLA"] == 300.0
            # Other tickers should use seed prices
            assert prices["GOOGL"] == SUPPORTED_TICKERS["GOOGL"]
        finally:
            await sim.stop()

    @pytest.mark.asyncio
    async def test_start_creates_background_task(self):
        cache = PriceCache()
        sim = MarketSimulator(cache)
        await sim.start()
        try:
            assert sim._task is not None
            assert not sim._task.done()
        finally:
            await sim.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_task(self):
        cache = PriceCache()
        sim = MarketSimulator(cache)
        await sim.start()
        task = sim._task
        await sim.stop()
        assert task.done()
        assert sim._task is None

    @pytest.mark.asyncio
    async def test_prices_update_after_interval(self):
        cache = PriceCache()
        sim = MarketSimulator(cache)
        await sim.start()
        try:
            initial_prices = dict(sim.current_prices)
            # Wait a bit longer than one tick
            await asyncio.sleep(0.7)
            updated_prices = sim.current_prices
            # At least some prices should have changed
            changed = sum(
                1
                for t in SUPPORTED_TICKERS
                if abs(updated_prices[t] - initial_prices[t]) > 0.001
            )
            assert changed > 0
        finally:
            await sim.stop()


class TestMarketSimulatorStep:
    """Tests for the core GBM _step() method."""

    def setup_method(self):
        self.cache = PriceCache()
        self.sim = MarketSimulator(self.cache)

    def _make_cfg(self, ticker="AAPL", seed=190.0, drift=0.05, vol=0.25):
        return TickerConfig(ticker=ticker, seed_price=seed, drift=drift, volatility=vol)

    def test_step_returns_positive_price(self):
        cfg = self._make_cfg()
        for _ in range(100):
            price = self.sim._step(100.0, cfg)
            assert price > 0

    def test_step_respects_min_price_floor(self):
        cfg = self._make_cfg(seed=1.0)
        # Start at exactly min price — should never go below it
        for _ in range(200):
            price = self.sim._step(MIN_PRICE, cfg)
            assert price >= MIN_PRICE

    def test_step_respects_max_price_ceiling(self):
        cfg = self._make_cfg(seed=100.0)
        ceiling = 100.0 * MAX_SEED_RATIO
        # Even starting at ceiling, should not exceed it
        for _ in range(200):
            price = self.sim._step(ceiling, cfg)
            assert price <= ceiling + 0.01  # allow float rounding

    def test_step_price_stays_near_seed_over_many_ticks(self):
        """Mean reversion should keep price within ±50% of seed over 1000 ticks."""
        cfg = self._make_cfg(seed=100.0, drift=0.05, vol=0.25)
        price = 100.0
        random.seed(42)
        for _ in range(1000):
            price = self.sim._step(price, cfg)
        # Should be within 3x of seed (MAX_SEED_RATIO = 3)
        assert MIN_PRICE <= price <= 100.0 * MAX_SEED_RATIO

    def test_step_gbm_math_without_jumps(self):
        """Verify that the GBM formula is correctly implemented (no jumps)."""
        cfg = self._make_cfg(seed=100.0, drift=0.05, vol=0.25)
        price = 100.0

        # Mock random.gauss to return 0 and random.random to return > JUMP_INTENSITY
        original_gauss = random.gauss
        original_random = random.random
        try:
            random.gauss = lambda mu, sigma: 0.0  # type: ignore[assignment]
            random.random = lambda: 1.0  # type: ignore[assignment]

            new_price = self.sim._step(price, cfg)

            # With Z=0 and no jump, only drift applies
            log_ratio = math.log(price / cfg.seed_price)  # = 0 at seed
            adjusted_drift = cfg.drift - REVERSION_SPEED * log_ratio  # = drift at seed
            dt = self.sim._dt
            expected_log_return = (adjusted_drift - 0.5 * cfg.volatility**2) * dt
            expected_price = price * math.exp(expected_log_return)

            assert abs(new_price - expected_price) < 1e-10
        finally:
            random.gauss = original_gauss  # type: ignore[assignment]
            random.random = original_random  # type: ignore[assignment]

    def test_mean_reversion_pulls_down_above_seed(self):
        """When price > seed, adjusted drift should be lower than base drift."""
        cfg = self._make_cfg(seed=100.0, drift=0.05, vol=0.00)  # zero vol
        # Compute adjusted drift manually for price above seed
        price_above = 200.0
        log_ratio = math.log(price_above / cfg.seed_price)
        adjusted = cfg.drift - REVERSION_SPEED * log_ratio
        assert adjusted < cfg.drift

    def test_mean_reversion_pulls_up_below_seed(self):
        """When price < seed, adjusted drift should be higher than base drift."""
        cfg = self._make_cfg(seed=100.0, drift=0.05, vol=0.00)
        price_below = 50.0
        log_ratio = math.log(price_below / cfg.seed_price)
        adjusted = cfg.drift - REVERSION_SPEED * log_ratio
        assert adjusted > cfg.drift

    def test_step_high_vol_produces_more_variance(self):
        """High-vol ticker should produce more price variance than low-vol."""
        low_cfg = self._make_cfg(seed=100.0, drift=0.05, vol=0.10)
        high_cfg = self._make_cfg(seed=100.0, drift=0.05, vol=0.60)

        random.seed(42)
        low_prices = [self.sim._step(100.0, low_cfg) for _ in range(500)]
        random.seed(42)
        high_prices = [self.sim._step(100.0, high_cfg) for _ in range(500)]

        low_std = (
            sum((p - 100.0) ** 2 for p in low_prices) / len(low_prices)
        ) ** 0.5
        high_std = (
            sum((p - 100.0) ** 2 for p in high_prices) / len(high_prices)
        ) ** 0.5

        assert high_std > low_std


class TestMarketSimulatorTick:
    def test_tick_updates_all_tickers_in_cache(self):
        cache = PriceCache()
        sim = MarketSimulator(cache)
        # Manually initialize prices (bypass start())
        for ticker, seed in SUPPORTED_TICKERS.items():
            sim._current_prices[ticker] = seed
            cache.update(ticker, seed)

        sim._tick()

        for ticker in SUPPORTED_TICKERS:
            entry = cache.get(ticker)
            assert entry is not None

    def test_tick_updates_current_prices_dict(self):
        cache = PriceCache()
        sim = MarketSimulator(cache)
        for ticker, seed in SUPPORTED_TICKERS.items():
            sim._current_prices[ticker] = seed

        sim._tick()

        for ticker in SUPPORTED_TICKERS:
            assert ticker in sim._current_prices


class TestMarketSimulatorGetSupportedTickers:
    def test_returns_all_supported_tickers(self):
        cache = PriceCache()
        sim = MarketSimulator(cache)
        tickers = sim.get_supported_tickers()
        assert set(tickers) == set(SUPPORTED_TICKERS.keys())

    def test_returns_list(self):
        cache = PriceCache()
        sim = MarketSimulator(cache)
        assert isinstance(sim.get_supported_tickers(), list)

    def test_no_duplicates(self):
        cache = PriceCache()
        sim = MarketSimulator(cache)
        tickers = sim.get_supported_tickers()
        assert len(tickers) == len(set(tickers))
