"""Deterministic mock LLM responses for testing (LLM_MOCK=true)."""

from __future__ import annotations

import re

from .models import LLMResponse, TradeAction, WatchlistChange


def mock_llm_response(user_message: str) -> LLMResponse:
    """Return a deterministic mock response based on keyword matching.

    Recognizes patterns like:
    - "buy 10 AAPL" / "buy AAPL"
    - "sell 5 TSLA" / "sell TSLA"
    - "add PYPL" / "add PYPL to watchlist"
    - "remove META" / "remove META from watchlist"
    - "portfolio" / "positions" / "holdings"
    - anything else -> generic helpful response
    """
    msg_lower = user_message.lower().strip()

    # Buy pattern: "buy [quantity] TICKER"
    buy_match = re.search(r"\bbuy\s+(\d+(?:\.\d+)?\s+)?([A-Z]{1,5})\b", user_message, re.IGNORECASE)
    if buy_match:
        qty_str = buy_match.group(1)
        ticker = buy_match.group(2).upper()
        quantity = float(qty_str.strip()) if qty_str else 10.0
        return LLMResponse(
            message=f"Executing buy order: {quantity} shares of {ticker} at market price.",
            trades=[TradeAction(ticker=ticker, side="buy", quantity=quantity)],
        )

    # Sell pattern: "sell [quantity] TICKER"
    sell_match = re.search(r"\bsell\s+(\d+(?:\.\d+)?\s+)?([A-Z]{1,5})\b", user_message, re.IGNORECASE)
    if sell_match:
        qty_str = sell_match.group(1)
        ticker = sell_match.group(2).upper()
        quantity = float(qty_str.strip()) if qty_str else 10.0
        return LLMResponse(
            message=f"Executing sell order: {quantity} shares of {ticker} at market price.",
            trades=[TradeAction(ticker=ticker, side="sell", quantity=quantity)],
        )

    # Watchlist add pattern
    add_match = re.search(r"\badd\s+([A-Z]{1,5})\b", user_message, re.IGNORECASE)
    if add_match:
        ticker = add_match.group(1).upper()
        return LLMResponse(
            message=f"Adding {ticker} to your watchlist.",
            watchlist_changes=[WatchlistChange(ticker=ticker, action="add")],
        )

    # Watchlist remove pattern
    remove_match = re.search(r"\bremove\s+([A-Z]{1,5})\b", user_message, re.IGNORECASE)
    if remove_match:
        ticker = remove_match.group(1).upper()
        return LLMResponse(
            message=f"Removing {ticker} from your watchlist.",
            watchlist_changes=[WatchlistChange(ticker=ticker, action="remove")],
        )

    # Portfolio inquiry
    if any(kw in msg_lower for kw in ("portfolio", "positions", "holdings", "balance", "p&l")):
        return LLMResponse(
            message=(
                "Your portfolio is looking good. You have a diversified set of positions. "
                "Consider reviewing your tech exposure — it's a large portion of your holdings."
            ),
        )

    # Default response
    return LLMResponse(
        message=(
            "I'm FinAlly, your AI trading assistant. I can help you buy or sell stocks, "
            "manage your watchlist, and analyze your portfolio. What would you like to do?"
        ),
    )
