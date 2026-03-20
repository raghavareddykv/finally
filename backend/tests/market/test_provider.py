"""Unit tests for market/__init__.py — create_market_provider factory."""

import os
from unittest.mock import patch

import pytest

from market import create_market_provider
from market.cache import PriceCache
from market.massive import MassivePoller
from market.simulator import MarketSimulator


class TestCreateMarketProvider:
    def test_returns_simulator_when_no_api_key(self):
        cache = PriceCache()
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MASSIVE_API_KEY", None)
            provider = create_market_provider(cache)
        assert isinstance(provider, MarketSimulator)

    def test_returns_simulator_when_api_key_empty(self):
        cache = PriceCache()
        with patch.dict(os.environ, {"MASSIVE_API_KEY": ""}):
            provider = create_market_provider(cache)
        assert isinstance(provider, MarketSimulator)

    def test_returns_simulator_when_api_key_whitespace_only(self):
        cache = PriceCache()
        with patch.dict(os.environ, {"MASSIVE_API_KEY": "   "}):
            provider = create_market_provider(cache)
        assert isinstance(provider, MarketSimulator)

    def test_returns_massive_poller_when_api_key_set(self):
        cache = PriceCache()
        with patch.dict(os.environ, {"MASSIVE_API_KEY": "real-api-key-123"}):
            provider = create_market_provider(cache)
        assert isinstance(provider, MassivePoller)

    def test_simulator_receives_cache(self):
        cache = PriceCache()
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MASSIVE_API_KEY", None)
            provider = create_market_provider(cache)
        assert isinstance(provider, MarketSimulator)
        assert provider._cache is cache

    def test_massive_poller_receives_cache_and_key(self):
        cache = PriceCache()
        api_key = "my-api-key"
        with patch.dict(os.environ, {"MASSIVE_API_KEY": api_key}):
            provider = create_market_provider(cache)
        assert isinstance(provider, MassivePoller)
        assert provider._cache is cache
        assert provider._api_key == api_key

    def test_provider_conforms_to_protocol(self):
        """Both providers must have start(), stop(), and get_supported_tickers()."""
        cache = PriceCache()

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MASSIVE_API_KEY", None)
            sim = create_market_provider(cache)

        with patch.dict(os.environ, {"MASSIVE_API_KEY": "key"}):
            massive = create_market_provider(cache)

        for provider in [sim, massive]:
            assert hasattr(provider, "start")
            assert hasattr(provider, "stop")
            assert hasattr(provider, "get_supported_tickers")
            assert callable(provider.start)
            assert callable(provider.stop)
            assert callable(provider.get_supported_tickers)
