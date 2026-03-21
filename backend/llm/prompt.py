"""System prompt and context construction for the FinAlly AI assistant."""

from __future__ import annotations

from typing import Any

SYSTEM_PROMPT = """\
You are FinAlly, an AI trading assistant built into a simulated trading workstation.
You help users analyze their portfolio, suggest trades, execute trades, and manage their watchlist.

## Capabilities
- Analyze portfolio composition, concentration risk, and P&L
- Suggest trades with clear reasoning
- Execute buy/sell trades when the user asks or agrees
- Add/remove tickers from the watchlist proactively
- Provide concise, data-driven market commentary

## Rules
- This is a simulated environment with virtual money — no real financial impact
- Only use tickers from the supported universe
- Market orders only, instant fill at current price, no fees
- Minimum trade quantity is 0.001 shares
- When executing trades, verify the user has sufficient cash (buys) or shares (sells)
- Be concise and data-driven — every word should earn its place
- Always respond with valid structured JSON matching the required schema

## Response Format
Always respond with JSON containing:
- "message": Your conversational response to the user
- "trades": Array of trades to execute (optional). Each: {"ticker": "AAPL", "side": "buy", "quantity": 10}
- "watchlist_changes": Array of watchlist changes (optional). Each: {"ticker": "PYPL", "action": "add"}

Only include trades or watchlist_changes when the user explicitly requests an action or agrees to your suggestion.\
"""


def build_portfolio_context(
    cash_balance: float,
    positions: list[dict[str, Any]],
    watchlist_prices: list[dict[str, Any]],
    total_value: float,
) -> str:
    """Build a concise portfolio context string for the LLM prompt."""
    lines = [
        "## Current Portfolio",
        f"Cash: ${cash_balance:,.2f}",
        f"Total Value: ${total_value:,.2f}",
    ]

    if positions:
        lines.append("\n### Positions")
        for pos in positions:
            ticker = pos["ticker"]
            qty = pos["quantity"]
            avg_cost = pos["avg_cost"]
            current_price = pos.get("current_price", avg_cost)
            unrealized_pnl = (current_price - avg_cost) * qty
            pnl_pct = ((current_price / avg_cost) - 1) * 100 if avg_cost > 0 else 0
            lines.append(
                f"- {ticker}: {qty} shares @ ${avg_cost:.2f} avg | "
                f"Current: ${current_price:.2f} | "
                f"P&L: ${unrealized_pnl:+,.2f} ({pnl_pct:+.1f}%)"
            )
    else:
        lines.append("\nNo open positions.")

    if watchlist_prices:
        lines.append("\n### Watchlist (live prices)")
        for wp in watchlist_prices:
            ticker = wp["ticker"]
            price = wp.get("price", 0)
            direction = wp.get("direction", "flat")
            arrow = {"up": "^", "down": "v", "flat": "-"}.get(direction, "-")
            lines.append(f"- {ticker}: ${price:.2f} {arrow}")

    return "\n".join(lines)


def build_messages(
    portfolio_context: str,
    chat_history: list[dict[str, str]],
    user_message: str,
) -> list[dict[str, str]]:
    """Assemble the full message list for the LLM call.

    Parameters
    ----------
    portfolio_context : str
        Formatted portfolio state (from build_portfolio_context).
    chat_history : list[dict]
        Previous messages, each with "role" and "content".
    user_message : str
        The new message from the user.
    """
    messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": portfolio_context},
    ]

    for msg in chat_history:
        messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": user_message})
    return messages
