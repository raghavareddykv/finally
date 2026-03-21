"""Chat service — orchestrates LLM calls, auto-execution, and persistence."""

from __future__ import annotations

import logging
import os
from typing import Any

from db.crud import (
    add_to_watchlist,
    create_chat_message,
    create_portfolio_snapshot,
    create_trade,
    get_cash_balance,
    get_chat_messages,
    get_position,
    get_positions,
    get_watchlist,
    is_ticker_in_watchlist,
    remove_from_watchlist,
    update_cash_balance,
    upsert_position,
)
from market.cache import PriceCache
from market.tickers import SUPPORTED_TICKERS

from .client import call_llm
from .mock import mock_llm_response
from .models import LLMResponse
from .prompt import build_messages, build_portfolio_context

logger = logging.getLogger(__name__)

MIN_QUANTITY = 0.001


def _is_mock_mode() -> bool:
    return os.environ.get("LLM_MOCK", "").lower() == "true"


async def _load_chat_history(limit: int = 20) -> list[dict[str, str]]:
    """Load the last *limit* chat messages for the default user."""
    messages = await get_chat_messages(limit=limit)
    return [{"role": m["role"], "content": m["content"]} for m in messages]


async def _load_portfolio_context(price_cache: PriceCache) -> dict[str, Any]:
    """Load cash, positions (with live prices), watchlist prices, and total value."""
    cash = await get_cash_balance()
    raw_positions = await get_positions()
    watchlist_entries = await get_watchlist()

    positions: list[dict[str, Any]] = []
    positions_value = 0.0
    for pos in raw_positions:
        ticker = pos["ticker"]
        current_price = price_cache.get_price(ticker) or pos["avg_cost"]
        positions.append({
            "ticker": ticker,
            "quantity": pos["quantity"],
            "avg_cost": pos["avg_cost"],
            "current_price": current_price,
        })
        positions_value += pos["quantity"] * current_price

    total_value = cash + positions_value

    watchlist_prices: list[dict[str, Any]] = []
    for entry in watchlist_entries:
        ticker = entry["ticker"]
        tp = price_cache.get(ticker)
        watchlist_prices.append({
            "ticker": ticker,
            "price": tp.price if tp else 0.0,
            "direction": tp.direction if tp else "flat",
        })

    return {
        "cash_balance": cash,
        "positions": positions,
        "watchlist_prices": watchlist_prices,
        "total_value": total_value,
    }


async def _execute_trade(
    ticker: str, side: str, quantity: float, price_cache: PriceCache
) -> dict[str, Any]:
    """Execute a single trade. Returns a result dict with status and details."""
    ticker = ticker.upper()

    if ticker not in SUPPORTED_TICKERS:
        return {"ticker": ticker, "side": side, "error": f"Invalid ticker: {ticker}"}

    current_price = price_cache.get_price(ticker)
    if current_price is None:
        return {"ticker": ticker, "side": side, "error": f"No price available for {ticker}"}

    if quantity < MIN_QUANTITY:
        return {"ticker": ticker, "side": side, "error": f"Minimum quantity is {MIN_QUANTITY}"}

    total_cost = quantity * current_price
    cash = await get_cash_balance()

    if side == "buy":
        if total_cost > cash:
            return {
                "ticker": ticker,
                "side": side,
                "error": f"Insufficient cash: need ${total_cost:,.2f}, have ${cash:,.2f}",
            }

        await update_cash_balance(cash - total_cost)

        existing = await get_position(ticker)
        if existing:
            old_qty = existing["quantity"]
            new_qty = old_qty + quantity
            new_avg = (old_qty * existing["avg_cost"] + quantity * current_price) / new_qty
        else:
            new_qty = quantity
            new_avg = current_price

        await upsert_position(ticker, new_qty, new_avg)

    elif side == "sell":
        existing = await get_position(ticker)
        if not existing or existing["quantity"] < quantity:
            held = existing["quantity"] if existing else 0
            return {
                "ticker": ticker,
                "side": side,
                "error": f"Insufficient shares: want to sell {quantity}, own {held}",
            }

        await update_cash_balance(cash + total_cost)
        new_qty = existing["quantity"] - quantity
        await upsert_position(ticker, new_qty, existing["avg_cost"])

    # Record the trade
    await create_trade(ticker, side, quantity, current_price)

    # Snapshot portfolio after trade
    new_cash = await get_cash_balance()
    all_positions = await get_positions()
    total_value = new_cash + sum(
        pos["quantity"] * (price_cache.get_price(pos["ticker"]) or pos["avg_cost"])
        for pos in all_positions
    )
    await create_portfolio_snapshot(round(total_value, 2))

    return {
        "ticker": ticker,
        "side": side,
        "quantity": quantity,
        "price": current_price,
        "total": round(total_cost, 2),
        "status": "executed",
    }


async def _execute_watchlist_change(ticker: str, action: str) -> dict[str, Any]:
    """Execute a single watchlist change. Returns a result dict."""
    ticker = ticker.upper()

    if action == "add":
        if ticker not in SUPPORTED_TICKERS:
            return {"ticker": ticker, "action": action, "error": f"Invalid ticker: {ticker}"}

        if await is_ticker_in_watchlist(ticker):
            return {"ticker": ticker, "action": "add", "error": "Already in watchlist"}

        await add_to_watchlist(ticker)
        return {"ticker": ticker, "action": "add", "status": "added"}

    elif action == "remove":
        pos = await get_position(ticker)
        if pos and pos["quantity"] > 0:
            return {
                "ticker": ticker,
                "action": "remove",
                "error": f"Cannot remove {ticker}: you hold a position in it",
            }

        removed = await remove_from_watchlist(ticker)
        if not removed:
            return {"ticker": ticker, "action": "remove", "error": "Not in watchlist"}
        return {"ticker": ticker, "action": "remove", "status": "removed"}

    return {"ticker": ticker, "action": action, "error": f"Unknown action: {action}"}


async def handle_chat_message(
    user_message: str,
    price_cache: PriceCache,
) -> dict[str, Any]:
    """Process a user chat message end-to-end.

    1. Store the user message
    2. Load portfolio context and chat history
    3. Call LLM (or mock) for a response
    4. Auto-execute any trades / watchlist changes
    5. Store the assistant response
    6. Return the full result to the caller
    """
    # 1. Store user message
    await create_chat_message(role="user", content=user_message)

    # 2. Get LLM response (mock or real)
    if _is_mock_mode():
        llm_response = mock_llm_response(user_message)
    else:
        try:
            context = await _load_portfolio_context(price_cache)
            portfolio_text = build_portfolio_context(**context)
            history = await _load_chat_history(limit=20)
            messages = build_messages(portfolio_text, history, user_message)
            llm_response = await call_llm(messages)
        except Exception as exc:
            logger.error("LLM call failed: %s", exc)
            llm_response = LLMResponse(
                message=f"I'm sorry, I encountered an error processing your request: {exc}"
            )

    # 3. Auto-execute trades
    trade_results: list[dict[str, Any]] = []
    for trade in llm_response.trades:
        result = await _execute_trade(
            ticker=trade.ticker,
            side=trade.side,
            quantity=trade.quantity,
            price_cache=price_cache,
        )
        trade_results.append(result)

    # 4. Auto-execute watchlist changes
    watchlist_results: list[dict[str, Any]] = []
    for change in llm_response.watchlist_changes:
        result = await _execute_watchlist_change(
            ticker=change.ticker, action=change.action
        )
        watchlist_results.append(result)

    # 5. Store assistant response with executed actions
    actions: dict[str, Any] = {}
    if trade_results:
        actions["trades"] = trade_results
    if watchlist_results:
        actions["watchlist_changes"] = watchlist_results

    await create_chat_message(
        role="assistant",
        content=llm_response.message,
        actions=actions if actions else None,
    )

    # 6. Return full result
    return {
        "message": llm_response.message,
        "trades": [t.model_dump() for t in llm_response.trades],
        "trade_results": trade_results,
        "watchlist_changes": [w.model_dump() for w in llm_response.watchlist_changes],
        "watchlist_results": watchlist_results,
    }
