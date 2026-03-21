"""Database package — connection management, schema, and CRUD operations.

Usage:
    from db import get_connection
    from db.crud import get_user, get_watchlist, create_trade
"""

from .connection import DB_PATH, get_connection, reset_initialization
from .crud import (
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
from .schema import DEFAULT_WATCHLIST_TICKERS, SCHEMA_SQL

__all__ = [
    # Connection
    "get_connection",
    "reset_initialization",
    "DB_PATH",
    # Schema
    "SCHEMA_SQL",
    "DEFAULT_WATCHLIST_TICKERS",
    # CRUD - Users
    "get_user",
    "get_cash_balance",
    "update_cash_balance",
    # CRUD - Watchlist
    "get_watchlist",
    "add_to_watchlist",
    "remove_from_watchlist",
    "is_ticker_in_watchlist",
    # CRUD - Positions
    "get_positions",
    "get_position",
    "upsert_position",
    # CRUD - Trades
    "create_trade",
    "get_trades",
    # CRUD - Portfolio Snapshots
    "create_portfolio_snapshot",
    "get_portfolio_snapshots",
    # CRUD - Chat
    "create_chat_message",
    "get_chat_messages",
]
