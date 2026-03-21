"""FinAlly — FastAPI application entry point.

Serves the API routes, SSE streaming, and static frontend files on port 8000.
"""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from db.connection import get_connection
from db.crud import (
    create_portfolio_snapshot,
    get_cash_balance,
    get_positions,
    get_watchlist,
)
from market import create_market_provider
from market.cache import PriceCache
from routes.health import router as health_router
from routes.portfolio import create_portfolio_router
from routes.stream import create_stream_router
from routes.chat import create_chat_router
from routes.watchlist import create_watchlist_router

# Load .env from project root
_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env")

# Shared state
cache = PriceCache()
provider = create_market_provider(cache)


async def _get_watchlist_tickers() -> list[str]:
    """Return the current user's watchlist ticker symbols."""
    entries = await get_watchlist()
    return [e["ticker"] for e in entries]


async def _snapshot_loop():
    """Record a portfolio snapshot every 30 seconds."""
    while True:
        await asyncio.sleep(30)
        try:
            cash = await get_cash_balance()
            positions = await get_positions()
            total_value = cash
            for pos in positions:
                price = cache.get_price(pos["ticker"])
                if price is None:
                    price = pos["avg_cost"]
                total_value += pos["quantity"] * price
            await create_portfolio_snapshot(round(total_value, 2))
        except Exception:
            pass  # Non-critical — skip and retry next cycle


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: start market data, init DB, run snapshot task."""
    # Initialize database (lazy init on first connection)
    conn = await get_connection()
    await conn.close()

    # Start market data provider
    await provider.start()

    # Start portfolio snapshot background task
    snapshot_task = asyncio.create_task(_snapshot_loop())

    yield

    # Shutdown
    snapshot_task.cancel()
    try:
        await snapshot_task
    except asyncio.CancelledError:
        pass
    await provider.stop()


app = FastAPI(title="FinAlly", lifespan=lifespan)

# API routes
app.include_router(health_router)
app.include_router(create_stream_router(cache, _get_watchlist_tickers))
app.include_router(create_portfolio_router(cache))
app.include_router(create_watchlist_router(cache))
app.include_router(create_chat_router(cache))

# Static file serving (frontend build output)
_static_dir = Path(__file__).resolve().parent.parent / "static"
if _static_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="static")
