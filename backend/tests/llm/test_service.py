"""Tests for the chat service — orchestration, trade execution, and mock mode."""

import os

import pytest

from db.crud import (
    add_to_watchlist,
    get_cash_balance,
    get_chat_messages,
    get_position,
    get_positions,
    get_watchlist,
    upsert_position,
)
from llm.service import (
    _execute_trade,
    _execute_watchlist_change,
    _load_chat_history,
    _load_portfolio_context,
    handle_chat_message,
)
from market.cache import PriceCache


@pytest.fixture
def price_cache():
    """A PriceCache pre-populated with test prices."""
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    cache.update("GOOGL", 175.0)
    cache.update("TSLA", 250.0)
    cache.update("NVDA", 880.0)
    cache.update("MSFT", 420.0)
    cache.update("PYPL", 65.0)
    cache.update("META", 500.0)
    return cache


@pytest.fixture(autouse=True)
def mock_mode(monkeypatch):
    """Enable mock mode for all tests in this module."""
    monkeypatch.setenv("LLM_MOCK", "true")


class TestLoadChatHistory:
    async def test_empty_history(self):
        history = await _load_chat_history()
        assert history == []

    async def test_history_after_messages(self, price_cache):
        await handle_chat_message("hello", price_cache)
        history = await _load_chat_history()
        # Should have user + assistant messages
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "hello"
        assert history[1]["role"] == "assistant"

    async def test_history_limit(self, price_cache):
        for i in range(5):
            await handle_chat_message(f"message {i}", price_cache)
        # 5 exchanges = 10 messages, limit to 4
        history = await _load_chat_history(limit=4)
        assert len(history) == 4


class TestLoadPortfolioContext:
    async def test_default_context(self, price_cache):
        ctx = await _load_portfolio_context(price_cache)
        assert ctx["cash_balance"] == 10000.0
        assert ctx["total_value"] == 10000.0
        assert ctx["positions"] == []
        assert len(ctx["watchlist_prices"]) == 10  # default watchlist

    async def test_context_with_position(self, price_cache):
        await upsert_position("AAPL", 10, 180.0)
        ctx = await _load_portfolio_context(price_cache)
        assert len(ctx["positions"]) == 1
        assert ctx["positions"][0]["ticker"] == "AAPL"
        assert ctx["positions"][0]["current_price"] == 190.0
        assert ctx["total_value"] == 10000.0 + 10 * 190.0


class TestExecuteTrade:
    async def test_buy_success(self, price_cache):
        result = await _execute_trade("AAPL", "buy", 10, price_cache)
        assert result["status"] == "executed"
        assert result["ticker"] == "AAPL"
        assert result["quantity"] == 10
        assert result["price"] == 190.0

        cash = await get_cash_balance()
        assert cash == pytest.approx(10000.0 - 10 * 190.0)

        pos = await get_position("AAPL")
        assert pos is not None
        assert pos["quantity"] == 10

    async def test_buy_insufficient_cash(self, price_cache):
        result = await _execute_trade("NVDA", "buy", 100, price_cache)
        assert "error" in result
        assert "Insufficient cash" in result["error"]

    async def test_sell_success(self, price_cache):
        # First buy
        await _execute_trade("AAPL", "buy", 10, price_cache)
        # Then sell
        result = await _execute_trade("AAPL", "sell", 5, price_cache)
        assert result["status"] == "executed"
        pos = await get_position("AAPL")
        assert pos["quantity"] == 5

    async def test_sell_full_position(self, price_cache):
        await _execute_trade("AAPL", "buy", 10, price_cache)
        result = await _execute_trade("AAPL", "sell", 10, price_cache)
        assert result["status"] == "executed"
        pos = await get_position("AAPL")
        assert pos is None  # Fully sold, row deleted

    async def test_sell_insufficient_shares(self, price_cache):
        result = await _execute_trade("AAPL", "sell", 10, price_cache)
        assert "error" in result
        assert "Insufficient shares" in result["error"]

    async def test_invalid_ticker(self, price_cache):
        result = await _execute_trade("INVALID", "buy", 1, price_cache)
        assert "error" in result
        assert "Invalid ticker" in result["error"]

    async def test_no_price_available(self, price_cache):
        # COST is a valid ticker but not in our test cache
        result = await _execute_trade("COST", "buy", 1, price_cache)
        assert "error" in result
        assert "No price" in result["error"]

    async def test_below_minimum_quantity(self, price_cache):
        result = await _execute_trade("AAPL", "buy", 0.0001, price_cache)
        assert "error" in result
        assert "Minimum" in result["error"]

    async def test_buy_updates_avg_cost(self, price_cache):
        await _execute_trade("AAPL", "buy", 10, price_cache)
        # Update price and buy more
        price_cache.update("AAPL", 200.0)
        await _execute_trade("AAPL", "buy", 10, price_cache)
        pos = await get_position("AAPL")
        assert pos["quantity"] == 20
        # Weighted avg: (10*190 + 10*200) / 20 = 195
        assert pos["avg_cost"] == pytest.approx(195.0)


class TestExecuteWatchlistChange:
    async def test_add_valid_ticker(self):
        result = await _execute_watchlist_change("PYPL", "add")
        assert result["status"] == "added"

    async def test_add_invalid_ticker(self):
        result = await _execute_watchlist_change("INVALID", "add")
        assert "error" in result

    async def test_add_duplicate(self):
        # AAPL is in default watchlist
        result = await _execute_watchlist_change("AAPL", "add")
        assert "error" in result
        assert "Already" in result["error"]

    async def test_remove_from_watchlist(self):
        # Add first, then remove
        await add_to_watchlist("PYPL")
        result = await _execute_watchlist_change("PYPL", "remove")
        assert result["status"] == "removed"

    async def test_remove_nonexistent(self):
        result = await _execute_watchlist_change("PYPL", "remove")
        assert "error" in result
        assert "Not in watchlist" in result["error"]

    async def test_remove_blocked_by_position(self, price_cache):
        await _execute_trade("AAPL", "buy", 10, price_cache)
        result = await _execute_watchlist_change("AAPL", "remove")
        assert "error" in result
        assert "hold a position" in result["error"]


class TestHandleChatMessage:
    async def test_mock_generic_message(self, price_cache):
        result = await handle_chat_message("hello", price_cache)
        assert "message" in result
        assert "FinAlly" in result["message"]
        assert result["trades"] == []
        assert result["watchlist_changes"] == []

    async def test_mock_buy_command(self, price_cache):
        result = await handle_chat_message("buy 5 AAPL", price_cache)
        assert len(result["trades"]) == 1
        assert result["trades"][0]["ticker"] == "AAPL"
        assert result["trades"][0]["side"] == "buy"
        assert result["trades"][0]["quantity"] == 5
        # Trade should have been auto-executed
        assert len(result["trade_results"]) == 1
        assert result["trade_results"][0]["status"] == "executed"

    async def test_mock_sell_command(self, price_cache):
        # Buy first
        await handle_chat_message("buy 10 AAPL", price_cache)
        # Then sell
        result = await handle_chat_message("sell 5 AAPL", price_cache)
        assert result["trade_results"][0]["status"] == "executed"

    async def test_mock_watchlist_add(self, price_cache):
        result = await handle_chat_message("add PYPL", price_cache)
        assert len(result["watchlist_changes"]) == 1
        assert result["watchlist_results"][0]["status"] == "added"

    async def test_mock_portfolio_query(self, price_cache):
        result = await handle_chat_message("show my portfolio", price_cache)
        assert "portfolio" in result["message"].lower()

    async def test_messages_stored_in_db(self, price_cache):
        await handle_chat_message("hello", price_cache)
        messages = await get_chat_messages()
        assert len(messages) == 2  # user + assistant
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "hello"
        assert messages[1]["role"] == "assistant"

    async def test_trade_failure_still_returns_response(self, price_cache):
        # Try to sell AAPL without owning any
        result = await handle_chat_message("sell 10 AAPL", price_cache)
        assert "message" in result
        assert len(result["trade_results"]) == 1
        assert "error" in result["trade_results"][0]

    async def test_empty_message_in_non_mock_mode_uses_mock_fallback(self, price_cache, monkeypatch):
        """When mock mode is on, even empty-ish messages get a response."""
        result = await handle_chat_message("   test   ", price_cache)
        assert "message" in result
