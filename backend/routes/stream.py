"""SSE price streaming endpoint.

Streams live price updates for the user's watchlist tickers at ~500ms cadence.
"""

import asyncio
import json

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from market.cache import PriceCache

router = APIRouter()


async def _price_generator(request: Request, cache: PriceCache, get_watchlist_tickers):
    """Yield SSE events with price updates for the user's watchlist."""
    while True:
        if await request.is_disconnected():
            break

        tickers = await get_watchlist_tickers()
        prices = cache.get_many(tickers)

        for tp in prices:
            data = json.dumps({
                "ticker": tp.ticker,
                "price": tp.price,
                "previous_price": tp.previous_price,
                "timestamp": tp.timestamp,
                "direction": tp.direction,
            })
            yield {"event": "price_update", "data": data}

        await asyncio.sleep(0.5)


def create_stream_router(cache: PriceCache, get_watchlist_tickers) -> APIRouter:
    """Create the stream router with injected dependencies.

    Args:
        cache: The shared PriceCache instance.
        get_watchlist_tickers: Async callable returning list[str] of the user's
            current watchlist tickers.
    """
    stream_router = APIRouter(prefix="/api/stream", tags=["stream"])

    @stream_router.get("/prices")
    async def stream_prices(request: Request):
        return EventSourceResponse(
            _price_generator(request, cache, get_watchlist_tickers)
        )

    return stream_router
