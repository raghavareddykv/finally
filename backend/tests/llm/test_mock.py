"""Tests for deterministic mock LLM responses."""

from llm.mock import mock_llm_response


class TestMockBuy:
    def test_buy_with_quantity(self):
        r = mock_llm_response("buy 10 AAPL")
        assert len(r.trades) == 1
        assert r.trades[0].ticker == "AAPL"
        assert r.trades[0].side == "buy"
        assert r.trades[0].quantity == 10.0

    def test_buy_without_quantity(self):
        r = mock_llm_response("buy TSLA")
        assert len(r.trades) == 1
        assert r.trades[0].ticker == "TSLA"
        assert r.trades[0].side == "buy"
        assert r.trades[0].quantity == 10.0  # default

    def test_buy_fractional(self):
        r = mock_llm_response("buy 0.5 NVDA")
        assert r.trades[0].quantity == 0.5

    def test_buy_case_insensitive(self):
        r = mock_llm_response("Buy 5 msft")
        assert r.trades[0].ticker == "MSFT"


class TestMockSell:
    def test_sell_with_quantity(self):
        r = mock_llm_response("sell 5 GOOGL")
        assert len(r.trades) == 1
        assert r.trades[0].ticker == "GOOGL"
        assert r.trades[0].side == "sell"
        assert r.trades[0].quantity == 5.0

    def test_sell_without_quantity(self):
        r = mock_llm_response("sell META")
        assert r.trades[0].side == "sell"
        assert r.trades[0].quantity == 10.0  # default


class TestMockWatchlist:
    def test_add_ticker(self):
        r = mock_llm_response("add PYPL")
        assert len(r.watchlist_changes) == 1
        assert r.watchlist_changes[0].ticker == "PYPL"
        assert r.watchlist_changes[0].action == "add"

    def test_remove_ticker(self):
        r = mock_llm_response("remove NFLX")
        assert len(r.watchlist_changes) == 1
        assert r.watchlist_changes[0].ticker == "NFLX"
        assert r.watchlist_changes[0].action == "remove"


class TestMockPortfolio:
    def test_portfolio_keyword(self):
        r = mock_llm_response("show my portfolio")
        assert "portfolio" in r.message.lower()
        assert r.trades == []
        assert r.watchlist_changes == []

    def test_positions_keyword(self):
        r = mock_llm_response("what are my positions?")
        assert r.trades == []

    def test_balance_keyword(self):
        r = mock_llm_response("check my balance")
        assert r.trades == []


class TestMockDefault:
    def test_generic_message(self):
        r = mock_llm_response("hello there")
        assert "FinAlly" in r.message
        assert r.trades == []
        assert r.watchlist_changes == []

    def test_empty_message(self):
        r = mock_llm_response("")
        assert r.message != ""
