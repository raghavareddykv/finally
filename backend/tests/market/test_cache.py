"""Unit tests for market/cache.py — PriceCache and TickerPrice."""

import time

import pytest

from market.cache import PriceCache, TickerPrice


class TestTickerPrice:
    def test_is_dataclass_with_slots(self):
        tp = TickerPrice(
            ticker="AAPL",
            price=190.0,
            previous_price=189.0,
            timestamp=1000.0,
            direction="up",
        )
        assert tp.ticker == "AAPL"
        assert tp.price == 190.0
        assert tp.previous_price == 189.0
        assert tp.timestamp == 1000.0
        assert tp.direction == "up"

    def test_slots_prevent_arbitrary_attributes(self):
        tp = TickerPrice("AAPL", 190.0, 189.0, 1000.0, "up")
        with pytest.raises(AttributeError):
            tp.nonexistent = "value"  # type: ignore[attr-defined]


class TestPriceCache:
    def setup_method(self):
        self.cache = PriceCache()

    # --- update() ---

    def test_update_returns_ticker_price(self):
        entry = self.cache.update("AAPL", 190.0)
        assert isinstance(entry, TickerPrice)
        assert entry.ticker == "AAPL"
        assert entry.price == 190.0

    def test_first_update_has_flat_direction(self):
        entry = self.cache.update("AAPL", 190.0)
        assert entry.direction == "flat"
        assert entry.previous_price == 190.0

    def test_price_increase_sets_direction_up(self):
        self.cache.update("AAPL", 190.0)
        entry = self.cache.update("AAPL", 191.0)
        assert entry.direction == "up"
        assert entry.previous_price == 190.0
        assert entry.price == 191.0

    def test_price_decrease_sets_direction_down(self):
        self.cache.update("AAPL", 191.0)
        entry = self.cache.update("AAPL", 189.0)
        assert entry.direction == "down"
        assert entry.previous_price == 191.0
        assert entry.price == 189.0

    def test_same_price_sets_direction_flat(self):
        self.cache.update("AAPL", 190.0)
        entry = self.cache.update("AAPL", 190.0)
        assert entry.direction == "flat"

    def test_price_is_rounded_to_2_decimals(self):
        entry = self.cache.update("AAPL", 190.12345)
        assert entry.price == 190.12

    def test_previous_price_is_rounded_to_2_decimals(self):
        self.cache.update("AAPL", 190.12345)
        entry = self.cache.update("AAPL", 191.0)
        assert entry.previous_price == 190.12

    def test_timestamp_is_recent(self):
        before = time.time()
        entry = self.cache.update("AAPL", 190.0)
        after = time.time()
        assert before <= entry.timestamp <= after

    def test_multiple_tickers_are_independent(self):
        self.cache.update("AAPL", 190.0)
        self.cache.update("TSLA", 250.0)
        self.cache.update("AAPL", 195.0)
        self.cache.update("TSLA", 240.0)

        aapl = self.cache.get("AAPL")
        tsla = self.cache.get("TSLA")

        assert aapl.price == 195.0
        assert aapl.direction == "up"
        assert tsla.price == 240.0
        assert tsla.direction == "down"

    # --- get() ---

    def test_get_returns_none_for_missing_ticker(self):
        assert self.cache.get("ZZZZ") is None

    def test_get_returns_latest_entry(self):
        self.cache.update("AAPL", 190.0)
        self.cache.update("AAPL", 195.0)
        entry = self.cache.get("AAPL")
        assert entry.price == 195.0

    # --- get_many() ---

    def test_get_many_returns_present_tickers(self):
        self.cache.update("AAPL", 190.0)
        self.cache.update("MSFT", 420.0)
        entries = self.cache.get_many(["AAPL", "MSFT"])
        assert len(entries) == 2
        tickers = {e.ticker for e in entries}
        assert tickers == {"AAPL", "MSFT"}

    def test_get_many_skips_missing_tickers(self):
        self.cache.update("AAPL", 190.0)
        entries = self.cache.get_many(["AAPL", "ZZZZ"])
        assert len(entries) == 1
        assert entries[0].ticker == "AAPL"

    def test_get_many_empty_list(self):
        assert self.cache.get_many([]) == []

    def test_get_many_all_missing(self):
        assert self.cache.get_many(["ZZZZ", "YYYY"]) == []

    # --- get_price() ---

    def test_get_price_returns_float(self):
        self.cache.update("AAPL", 190.0)
        assert self.cache.get_price("AAPL") == 190.0

    def test_get_price_returns_none_for_missing(self):
        assert self.cache.get_price("ZZZZ") is None

    # --- all_tickers() ---

    def test_all_tickers_empty_on_init(self):
        assert self.cache.all_tickers() == []

    def test_all_tickers_returns_all_updated(self):
        self.cache.update("AAPL", 190.0)
        self.cache.update("TSLA", 250.0)
        assert set(self.cache.all_tickers()) == {"AAPL", "TSLA"}

    def test_all_tickers_no_duplicates_after_repeated_update(self):
        self.cache.update("AAPL", 190.0)
        self.cache.update("AAPL", 195.0)
        assert self.cache.all_tickers().count("AAPL") == 1
