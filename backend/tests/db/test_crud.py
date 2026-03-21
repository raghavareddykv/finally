"""Tests for database CRUD operations."""

import pytest

from db.crud import (
    add_to_watchlist,
    create_chat_message,
    create_portfolio_snapshot,
    create_trade,
    get_cash_balance,
    get_chat_messages,
    get_portfolio_snapshots,
    get_position,
    get_positions,
    get_trades,
    get_user,
    get_watchlist,
    is_ticker_in_watchlist,
    remove_from_watchlist,
    update_cash_balance,
    upsert_position,
)


class TestUsersCrud:
    async def test_get_default_user(self):
        user = await get_user()
        assert user is not None
        assert user["id"] == "default"
        assert user["cash_balance"] == 10000.0
        assert "created_at" in user

    async def test_get_nonexistent_user(self):
        user = await get_user("nobody")
        assert user is None

    async def test_get_cash_balance(self):
        balance = await get_cash_balance()
        assert balance == 10000.0

    async def test_get_cash_balance_unknown_user_raises(self):
        with pytest.raises(ValueError, match="not found"):
            await get_cash_balance("nobody")

    async def test_update_cash_balance(self):
        await update_cash_balance(7500.50)
        assert await get_cash_balance() == 7500.50

    async def test_update_cash_balance_to_zero(self):
        await update_cash_balance(0.0)
        assert await get_cash_balance() == 0.0


class TestWatchlistCrud:
    async def test_default_watchlist_has_10_entries(self):
        wl = await get_watchlist()
        assert len(wl) == 10
        tickers = {w["ticker"] for w in wl}
        assert "AAPL" in tickers
        assert "NFLX" in tickers

    async def test_add_to_watchlist(self):
        entry = await add_to_watchlist("PYPL")
        assert entry["ticker"] == "PYPL"
        assert "id" in entry
        assert "added_at" in entry
        wl = await get_watchlist()
        assert len(wl) == 11

    async def test_add_duplicate_ticker_raises(self):
        with pytest.raises(Exception):  # IntegrityError from UNIQUE constraint
            await add_to_watchlist("AAPL")

    async def test_add_normalizes_to_uppercase(self):
        entry = await add_to_watchlist("pypl")
        assert entry["ticker"] == "PYPL"

    async def test_remove_from_watchlist(self):
        removed = await remove_from_watchlist("AAPL")
        assert removed is True
        wl = await get_watchlist()
        tickers = {w["ticker"] for w in wl}
        assert "AAPL" not in tickers
        assert len(wl) == 9

    async def test_remove_nonexistent_ticker(self):
        removed = await remove_from_watchlist("FAKE")
        assert removed is False

    async def test_is_ticker_in_watchlist_true(self):
        assert await is_ticker_in_watchlist("AAPL") is True

    async def test_is_ticker_in_watchlist_false(self):
        assert await is_ticker_in_watchlist("FAKE") is False

    async def test_is_ticker_in_watchlist_case_insensitive(self):
        assert await is_ticker_in_watchlist("aapl") is True


class TestPositionsCrud:
    async def test_no_positions_initially(self):
        assert await get_positions() == []
        assert await get_position("AAPL") is None

    async def test_create_position(self):
        pos = await upsert_position("AAPL", 10.0, 190.0)
        assert pos is not None
        assert pos["ticker"] == "AAPL"
        assert pos["quantity"] == 10.0
        assert pos["avg_cost"] == 190.0

    async def test_update_position(self):
        await upsert_position("AAPL", 10.0, 190.0)
        pos = await upsert_position("AAPL", 20.0, 192.5)
        assert pos["quantity"] == 20.0
        assert pos["avg_cost"] == 192.5

    async def test_delete_position_at_zero_quantity(self):
        await upsert_position("AAPL", 10.0, 190.0)
        result = await upsert_position("AAPL", 0, 0)
        assert result is None
        assert await get_position("AAPL") is None

    async def test_delete_position_at_negative_quantity(self):
        await upsert_position("AAPL", 10.0, 190.0)
        result = await upsert_position("AAPL", -1, 0)
        assert result is None

    async def test_get_positions_returns_all(self):
        await upsert_position("AAPL", 10.0, 190.0)
        await upsert_position("GOOGL", 5.0, 175.0)
        positions = await get_positions()
        assert len(positions) == 2
        tickers = {p["ticker"] for p in positions}
        assert tickers == {"AAPL", "GOOGL"}

    async def test_position_ticker_normalized_uppercase(self):
        pos = await upsert_position("aapl", 10.0, 190.0)
        assert pos["ticker"] == "AAPL"

    async def test_fractional_shares(self):
        pos = await upsert_position("AAPL", 0.001, 190.0)
        assert pos["quantity"] == 0.001


class TestTradesCrud:
    async def test_create_trade(self):
        trade = await create_trade("AAPL", "buy", 10.0, 190.0)
        assert trade["ticker"] == "AAPL"
        assert trade["side"] == "buy"
        assert trade["quantity"] == 10.0
        assert trade["price"] == 190.0
        assert "id" in trade
        assert "executed_at" in trade

    async def test_get_trades_newest_first(self):
        await create_trade("AAPL", "buy", 10.0, 190.0)
        await create_trade("GOOGL", "buy", 5.0, 175.0)
        trades = await get_trades()
        assert len(trades) == 2
        # Newest first
        assert trades[0]["ticker"] == "GOOGL"
        assert trades[1]["ticker"] == "AAPL"

    async def test_get_trades_respects_limit(self):
        for i in range(5):
            await create_trade("AAPL", "buy", 1.0, 190.0 + i)
        trades = await get_trades(limit=3)
        assert len(trades) == 3

    async def test_create_sell_trade(self):
        trade = await create_trade("AAPL", "sell", 5.0, 195.0)
        assert trade["side"] == "sell"


class TestPortfolioSnapshotsCrud:
    async def test_create_snapshot(self):
        snap = await create_portfolio_snapshot(10500.0)
        assert snap["total_value"] == 10500.0
        assert "id" in snap
        assert "recorded_at" in snap

    async def test_get_snapshots_oldest_first(self):
        await create_portfolio_snapshot(10000.0)
        await create_portfolio_snapshot(10500.0)
        await create_portfolio_snapshot(10200.0)
        snaps = await get_portfolio_snapshots()
        assert len(snaps) == 3
        # Oldest first (for charting)
        assert snaps[0]["total_value"] == 10000.0
        assert snaps[2]["total_value"] == 10200.0

    async def test_get_snapshots_respects_limit(self):
        for i in range(10):
            await create_portfolio_snapshot(10000.0 + i * 100)
        snaps = await get_portfolio_snapshots(limit=5)
        assert len(snaps) == 5


class TestChatMessagesCrud:
    async def test_create_user_message(self):
        msg = await create_chat_message("user", "Buy AAPL")
        assert msg["role"] == "user"
        assert msg["content"] == "Buy AAPL"
        assert msg["actions"] is None

    async def test_create_assistant_message_with_actions(self):
        actions = {"trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}]}
        msg = await create_chat_message("assistant", "Done!", actions=actions)
        assert msg["role"] == "assistant"
        # Stored as JSON string
        assert '"trades"' in msg["actions"]

    async def test_get_messages_oldest_first(self):
        await create_chat_message("user", "Hello")
        await create_chat_message("assistant", "Hi there!")
        await create_chat_message("user", "Buy AAPL")
        msgs = await get_chat_messages()
        assert len(msgs) == 3
        assert msgs[0]["content"] == "Hello"
        assert msgs[2]["content"] == "Buy AAPL"

    async def test_get_messages_respects_limit(self):
        for i in range(30):
            await create_chat_message("user", f"Message {i}")
        msgs = await get_chat_messages(limit=20)
        assert len(msgs) == 20
        # Should be the LAST 20 messages, oldest first
        assert msgs[0]["content"] == "Message 10"
        assert msgs[-1]["content"] == "Message 29"

    async def test_get_messages_deserializes_actions(self):
        actions = {"trades": [{"ticker": "AAPL", "side": "buy", "quantity": 5}]}
        await create_chat_message("assistant", "Bought!", actions=actions)
        msgs = await get_chat_messages()
        assert msgs[0]["actions"] == actions  # Deserialized dict, not JSON string

    async def test_actions_none_for_user_messages(self):
        await create_chat_message("user", "Hello")
        msgs = await get_chat_messages()
        assert msgs[0]["actions"] is None

    async def test_actions_with_list_value(self):
        actions = [{"action": "add", "ticker": "PYPL"}]
        msg = await create_chat_message("assistant", "Added!", actions=actions)
        msgs = await get_chat_messages()
        assert msgs[0]["actions"] == actions
