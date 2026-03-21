"""Async CRUD operations for the FinAlly database.

All functions accept a user_id parameter defaulting to "default".
"""

import json
import uuid
from datetime import datetime, timezone

from .connection import get_connection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Users / Cash
# ---------------------------------------------------------------------------

async def get_user(user_id: str = "default") -> dict | None:
    """Get user profile (id, cash_balance, created_at)."""
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "SELECT id, cash_balance, created_at FROM users_profile WHERE id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await conn.close()


async def get_cash_balance(user_id: str = "default") -> float:
    """Return the user's current cash balance."""
    user = await get_user(user_id)
    if user is None:
        raise ValueError(f"User {user_id!r} not found")
    return user["cash_balance"]


async def update_cash_balance(new_balance: float, user_id: str = "default") -> None:
    """Set the user's cash balance to an absolute value."""
    conn = await get_connection()
    try:
        await conn.execute(
            "UPDATE users_profile SET cash_balance = ? WHERE id = ?",
            (new_balance, user_id),
        )
        await conn.commit()
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------

async def get_watchlist(user_id: str = "default") -> list[dict]:
    """Return all watchlist entries for the user."""
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "SELECT id, user_id, ticker, added_at FROM watchlist WHERE user_id = ? ORDER BY added_at",
            (user_id,),
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await conn.close()


async def add_to_watchlist(ticker: str, user_id: str = "default") -> dict:
    """Add a ticker to the watchlist. Returns the new entry."""
    entry = {
        "id": _uuid(),
        "user_id": user_id,
        "ticker": ticker.upper(),
        "added_at": _now(),
    }
    conn = await get_connection()
    try:
        await conn.execute(
            "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
            (entry["id"], entry["user_id"], entry["ticker"], entry["added_at"]),
        )
        await conn.commit()
        return entry
    finally:
        await conn.close()


async def remove_from_watchlist(ticker: str, user_id: str = "default") -> bool:
    """Remove a ticker from the watchlist. Returns True if a row was deleted."""
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?",
            (user_id, ticker.upper()),
        )
        await conn.commit()
        return cursor.rowcount > 0
    finally:
        await conn.close()


async def is_ticker_in_watchlist(ticker: str, user_id: str = "default") -> bool:
    """Check if a ticker is in the user's watchlist."""
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "SELECT 1 FROM watchlist WHERE user_id = ? AND ticker = ?",
            (user_id, ticker.upper()),
        )
        return await cursor.fetchone() is not None
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Positions
# ---------------------------------------------------------------------------

async def get_positions(user_id: str = "default") -> list[dict]:
    """Return all open positions for the user."""
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "SELECT id, user_id, ticker, quantity, avg_cost, updated_at "
            "FROM positions WHERE user_id = ? ORDER BY ticker",
            (user_id,),
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await conn.close()


async def get_position(ticker: str, user_id: str = "default") -> dict | None:
    """Return a single position for the given ticker, or None."""
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "SELECT id, user_id, ticker, quantity, avg_cost, updated_at "
            "FROM positions WHERE user_id = ? AND ticker = ?",
            (user_id, ticker.upper()),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await conn.close()


async def upsert_position(
    ticker: str, quantity: float, avg_cost: float, user_id: str = "default"
) -> dict | None:
    """Create or update a position. Deletes the row if quantity reaches zero.

    Returns the position dict, or None if the position was deleted.
    """
    ticker = ticker.upper()
    now = _now()
    conn = await get_connection()
    try:
        if quantity <= 0:
            await conn.execute(
                "DELETE FROM positions WHERE user_id = ? AND ticker = ?",
                (user_id, ticker),
            )
            await conn.commit()
            return None

        # Try update first
        cursor = await conn.execute(
            "UPDATE positions SET quantity = ?, avg_cost = ?, updated_at = ? "
            "WHERE user_id = ? AND ticker = ?",
            (quantity, avg_cost, now, user_id, ticker),
        )
        if cursor.rowcount == 0:
            # Insert new
            pos_id = _uuid()
            await conn.execute(
                "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (pos_id, user_id, ticker, quantity, avg_cost, now),
            )
        else:
            pos_id = None  # Will fetch below

        await conn.commit()

        # Fetch and return the current state
        cursor = await conn.execute(
            "SELECT id, user_id, ticker, quantity, avg_cost, updated_at "
            "FROM positions WHERE user_id = ? AND ticker = ?",
            (user_id, ticker),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Trades
# ---------------------------------------------------------------------------

async def create_trade(
    ticker: str,
    side: str,
    quantity: float,
    price: float,
    user_id: str = "default",
) -> dict:
    """Record a trade. Returns the trade dict."""
    trade = {
        "id": _uuid(),
        "user_id": user_id,
        "ticker": ticker.upper(),
        "side": side,
        "quantity": quantity,
        "price": price,
        "executed_at": _now(),
    }
    conn = await get_connection()
    try:
        await conn.execute(
            "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (trade["id"], trade["user_id"], trade["ticker"], trade["side"],
             trade["quantity"], trade["price"], trade["executed_at"]),
        )
        await conn.commit()
        return trade
    finally:
        await conn.close()


async def get_trades(user_id: str = "default", limit: int = 50) -> list[dict]:
    """Return recent trades, newest first."""
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "SELECT id, user_id, ticker, side, quantity, price, executed_at "
            "FROM trades WHERE user_id = ? ORDER BY executed_at DESC LIMIT ?",
            (user_id, limit),
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Portfolio Snapshots
# ---------------------------------------------------------------------------

async def create_portfolio_snapshot(
    total_value: float, user_id: str = "default"
) -> dict:
    """Record a portfolio value snapshot."""
    snapshot = {
        "id": _uuid(),
        "user_id": user_id,
        "total_value": total_value,
        "recorded_at": _now(),
    }
    conn = await get_connection()
    try:
        await conn.execute(
            "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) "
            "VALUES (?, ?, ?, ?)",
            (snapshot["id"], snapshot["user_id"], snapshot["total_value"],
             snapshot["recorded_at"]),
        )
        await conn.commit()
        return snapshot
    finally:
        await conn.close()


async def get_portfolio_snapshots(
    user_id: str = "default", limit: int = 500
) -> list[dict]:
    """Return portfolio snapshots, oldest first (for charting)."""
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "SELECT id, user_id, total_value, recorded_at "
            "FROM portfolio_snapshots WHERE user_id = ? "
            "ORDER BY recorded_at ASC LIMIT ?",
            (user_id, limit),
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Chat Messages
# ---------------------------------------------------------------------------

async def create_chat_message(
    role: str,
    content: str,
    actions: dict | list | None = None,
    user_id: str = "default",
) -> dict:
    """Store a chat message. Actions is serialized to JSON."""
    message = {
        "id": _uuid(),
        "user_id": user_id,
        "role": role,
        "content": content,
        "actions": json.dumps(actions) if actions is not None else None,
        "created_at": _now(),
    }
    conn = await get_connection()
    try:
        await conn.execute(
            "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (message["id"], message["user_id"], message["role"],
             message["content"], message["actions"], message["created_at"]),
        )
        await conn.commit()
        return message
    finally:
        await conn.close()


async def get_chat_messages(
    user_id: str = "default", limit: int = 20
) -> list[dict]:
    """Return the last N chat messages, oldest first.

    The actions field is deserialized from JSON.
    """
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "SELECT id, user_id, role, content, actions, created_at "
            "FROM chat_messages WHERE user_id = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        )
        rows = [dict(row) for row in await cursor.fetchall()]
        # Reverse to get oldest-first ordering
        rows.reverse()
        # Deserialize actions JSON
        for row in rows:
            if row["actions"] is not None:
                row["actions"] = json.loads(row["actions"])
        return rows
    finally:
        await conn.close()
