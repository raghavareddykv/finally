"""Tests for LLM structured output Pydantic models."""

import json

import pytest

from llm.models import LLMResponse, TradeAction, WatchlistChange


class TestTradeAction:
    def test_valid_buy(self):
        t = TradeAction(ticker="AAPL", side="buy", quantity=10.0)
        assert t.ticker == "AAPL"
        assert t.side == "buy"
        assert t.quantity == 10.0

    def test_valid_sell(self):
        t = TradeAction(ticker="TSLA", side="sell", quantity=5.5)
        assert t.side == "sell"
        assert t.quantity == 5.5

    def test_invalid_side(self):
        with pytest.raises(Exception):
            TradeAction(ticker="AAPL", side="hold", quantity=1)


class TestWatchlistChange:
    def test_valid_add(self):
        w = WatchlistChange(ticker="PYPL", action="add")
        assert w.ticker == "PYPL"
        assert w.action == "add"

    def test_valid_remove(self):
        w = WatchlistChange(ticker="META", action="remove")
        assert w.action == "remove"

    def test_invalid_action(self):
        with pytest.raises(Exception):
            WatchlistChange(ticker="META", action="toggle")


class TestLLMResponse:
    def test_message_only(self):
        r = LLMResponse(message="Hello!")
        assert r.message == "Hello!"
        assert r.trades == []
        assert r.watchlist_changes == []

    def test_with_trades(self):
        r = LLMResponse(
            message="Buying AAPL",
            trades=[TradeAction(ticker="AAPL", side="buy", quantity=10)],
        )
        assert len(r.trades) == 1
        assert r.trades[0].ticker == "AAPL"

    def test_with_watchlist_changes(self):
        r = LLMResponse(
            message="Adding PYPL",
            watchlist_changes=[WatchlistChange(ticker="PYPL", action="add")],
        )
        assert len(r.watchlist_changes) == 1

    def test_full_response(self):
        r = LLMResponse(
            message="Done",
            trades=[
                TradeAction(ticker="AAPL", side="buy", quantity=5),
                TradeAction(ticker="TSLA", side="sell", quantity=2),
            ],
            watchlist_changes=[
                WatchlistChange(ticker="PYPL", action="add"),
            ],
        )
        assert len(r.trades) == 2
        assert len(r.watchlist_changes) == 1

    def test_parse_from_json(self):
        raw = json.dumps({
            "message": "Bought AAPL",
            "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}],
            "watchlist_changes": [],
        })
        r = LLMResponse.model_validate_json(raw)
        assert r.message == "Bought AAPL"
        assert len(r.trades) == 1

    def test_parse_minimal_json(self):
        raw = json.dumps({"message": "Hi there"})
        r = LLMResponse.model_validate_json(raw)
        assert r.message == "Hi there"
        assert r.trades == []
        assert r.watchlist_changes == []

    def test_parse_invalid_json_raises(self):
        with pytest.raises(Exception):
            LLMResponse.model_validate_json("not json")

    def test_parse_missing_message_raises(self):
        with pytest.raises(Exception):
            LLMResponse.model_validate_json(json.dumps({"trades": []}))

    def test_model_dump(self):
        r = LLMResponse(
            message="test",
            trades=[TradeAction(ticker="AAPL", side="buy", quantity=1)],
        )
        d = r.model_dump()
        assert d["message"] == "test"
        assert len(d["trades"]) == 1
        assert d["trades"][0]["ticker"] == "AAPL"
