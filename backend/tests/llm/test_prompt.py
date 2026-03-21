"""Tests for prompt construction."""

from llm.prompt import SYSTEM_PROMPT, build_messages, build_portfolio_context


class TestBuildPortfolioContext:
    def test_basic_context(self):
        text = build_portfolio_context(
            cash_balance=10000.0,
            positions=[],
            watchlist_prices=[],
            total_value=10000.0,
        )
        assert "$10,000.00" in text
        assert "No open positions" in text

    def test_with_positions(self):
        text = build_portfolio_context(
            cash_balance=5000.0,
            positions=[
                {
                    "ticker": "AAPL",
                    "quantity": 10,
                    "avg_cost": 180.0,
                    "current_price": 190.0,
                }
            ],
            watchlist_prices=[],
            total_value=6900.0,
        )
        assert "AAPL" in text
        assert "10 shares" in text
        assert "180.00" in text
        assert "190.00" in text

    def test_with_watchlist(self):
        text = build_portfolio_context(
            cash_balance=10000.0,
            positions=[],
            watchlist_prices=[
                {"ticker": "TSLA", "price": 250.0, "direction": "up"},
                {"ticker": "GOOGL", "price": 175.0, "direction": "down"},
            ],
            total_value=10000.0,
        )
        assert "TSLA" in text
        assert "250.00" in text
        assert "^" in text  # up arrow
        assert "v" in text  # down arrow

    def test_pnl_calculation_in_context(self):
        text = build_portfolio_context(
            cash_balance=0,
            positions=[
                {
                    "ticker": "NVDA",
                    "quantity": 1,
                    "avg_cost": 800.0,
                    "current_price": 900.0,
                }
            ],
            watchlist_prices=[],
            total_value=900.0,
        )
        assert "$+100.00" in text
        assert "+12.5%" in text


class TestBuildMessages:
    def test_minimal_messages(self):
        msgs = build_messages(
            portfolio_context="Cash: $10000",
            chat_history=[],
            user_message="hello",
        )
        assert len(msgs) == 3  # system prompt + portfolio context + user
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "system"
        assert msgs[2]["role"] == "user"
        assert msgs[2]["content"] == "hello"

    def test_with_history(self):
        history = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
        msgs = build_messages(
            portfolio_context="Cash: $10000",
            chat_history=history,
            user_message="new message",
        )
        # system + context + 2 history + new user message
        assert len(msgs) == 5
        assert msgs[2]["content"] == "hi"
        assert msgs[3]["content"] == "hello"
        assert msgs[4]["content"] == "new message"

    def test_system_prompt_content(self):
        msgs = build_messages("context", [], "msg")
        assert "FinAlly" in msgs[0]["content"]
        assert "trading assistant" in msgs[0]["content"]


class TestSystemPrompt:
    def test_has_json_instructions(self):
        assert "JSON" in SYSTEM_PROMPT

    def test_has_trade_format(self):
        assert "trades" in SYSTEM_PROMPT
        assert "watchlist_changes" in SYSTEM_PROMPT
