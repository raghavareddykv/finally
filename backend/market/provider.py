"""MarketDataProvider protocol — structural typing contract for market data providers.

Both MarketSimulator and MassivePoller conform to this protocol.
Downstream code (SSE, trade execution, portfolio valuation) depends only on PriceCache,
not on any specific provider.
"""

from typing import Protocol


class MarketDataProvider(Protocol):
    """Structural contract for market data providers.

    Implementations must be instantiated with a reference to a PriceCache
    and write updated prices into it on their own schedule.
    """

    async def start(self) -> None:
        """Begin generating/fetching prices. Called once at app startup."""
        ...

    async def stop(self) -> None:
        """Clean shutdown. Called once at app shutdown."""
        ...

    def get_supported_tickers(self) -> list[str]:
        """Return the list of tickers this provider knows about."""
        ...
