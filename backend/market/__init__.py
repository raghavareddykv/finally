"""Market data package — factory function and public re-exports.

Usage in FastAPI lifespan:
    from market import create_market_provider
    from market.cache import PriceCache

    cache = PriceCache()
    provider = create_market_provider(cache)

    @asynccontextmanager
    async def lifespan(app):
        await provider.start()
        yield
        await provider.stop()
"""

import os

from .cache import PriceCache
from .massive import MassivePoller
from .simulator import MarketSimulator


def create_market_provider(cache: PriceCache) -> MarketSimulator | MassivePoller:
    """Select and instantiate the appropriate market data provider.

    Uses MassivePoller if MASSIVE_API_KEY env var is set and non-empty,
    otherwise falls back to the built-in MarketSimulator.
    """
    api_key = os.environ.get("MASSIVE_API_KEY", "").strip()

    if api_key:
        return MassivePoller(cache=cache, api_key=api_key)
    else:
        return MarketSimulator(cache=cache)


__all__ = [
    "create_market_provider",
    "PriceCache",
    "MarketSimulator",
    "MassivePoller",
]
