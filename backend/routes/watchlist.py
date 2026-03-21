"""Watchlist API endpoints."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from db.crud import (
    add_to_watchlist,
    get_position,
    get_watchlist,
    is_ticker_in_watchlist,
    remove_from_watchlist,
)
from market.cache import PriceCache
from market.tickers import SUPPORTED_TICKERS


def create_watchlist_router(cache: PriceCache) -> APIRouter:
    """Create the watchlist router with injected PriceCache."""
    router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

    @router.get("")
    async def list_watchlist():
        entries = await get_watchlist()
        result = []
        for entry in entries:
            ticker = entry["ticker"]
            tp = cache.get(ticker)
            result.append({
                "ticker": ticker,
                "added_at": entry["added_at"],
                "price": tp.price if tp else None,
                "previous_price": tp.previous_price if tp else None,
                "direction": tp.direction if tp else None,
                "timestamp": tp.timestamp if tp else None,
            })
        return result

    @router.post("", status_code=201)
    async def add_ticker(body: dict):
        ticker = body.get("ticker", "").upper().strip()

        if ticker not in SUPPORTED_TICKERS:
            return JSONResponse(
                status_code=400,
                content={"error": f"Ticker '{ticker}' is not in the supported universe", "code": "INVALID_TICKER"},
            )

        if await is_ticker_in_watchlist(ticker):
            return JSONResponse(
                status_code=409,
                content={"error": f"Ticker '{ticker}' is already in your watchlist", "code": "TICKER_ALREADY_WATCHED"},
            )

        entry = await add_to_watchlist(ticker)
        tp = cache.get(ticker)
        return {
            "ticker": entry["ticker"],
            "added_at": entry["added_at"],
            "price": tp.price if tp else None,
            "previous_price": tp.previous_price if tp else None,
            "direction": tp.direction if tp else None,
            "timestamp": tp.timestamp if tp else None,
        }

    @router.delete("/{ticker}")
    async def remove_ticker(ticker: str):
        ticker = ticker.upper().strip()

        if ticker not in SUPPORTED_TICKERS:
            return JSONResponse(
                status_code=400,
                content={"error": f"Ticker '{ticker}' is not in the supported universe", "code": "INVALID_TICKER"},
            )

        position = await get_position(ticker)
        if position and position["quantity"] > 0:
            return JSONResponse(
                status_code=409,
                content={"error": f"Cannot remove '{ticker}' from watchlist while you hold a position", "code": "POSITION_EXISTS"},
            )

        removed = await remove_from_watchlist(ticker)
        if not removed:
            return JSONResponse(
                status_code=404,
                content={"error": f"Ticker '{ticker}' is not in your watchlist", "code": "TICKER_NOT_FOUND"},
            )

        return {"message": f"Removed '{ticker}' from watchlist"}

    return router
