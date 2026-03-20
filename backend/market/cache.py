"""In-memory price cache — the shared state between market data providers and consumers."""

import time
from dataclasses import dataclass


@dataclass(slots=True)
class TickerPrice:
    """Immutable snapshot of a ticker's current price state."""

    ticker: str
    price: float
    previous_price: float
    timestamp: float
    direction: str  # "up" | "down" | "flat"


class PriceCache:
    """In-memory latest-price cache. One entry per ticker.

    Safe for single-process asyncio (cooperative scheduling, no concurrent writes).
    """

    def __init__(self) -> None:
        self._prices: dict[str, TickerPrice] = {}

    def update(self, ticker: str, new_price: float) -> TickerPrice:
        """Write a new price. Computes direction from previous value."""
        now = time.time()
        prev = self._prices.get(ticker)
        previous_price = prev.price if prev else new_price

        if new_price > previous_price:
            direction = "up"
        elif new_price < previous_price:
            direction = "down"
        else:
            direction = "flat"

        entry = TickerPrice(
            ticker=ticker,
            price=round(new_price, 2),
            previous_price=round(previous_price, 2),
            timestamp=now,
            direction=direction,
        )
        self._prices[ticker] = entry
        return entry

    def get(self, ticker: str) -> TickerPrice | None:
        """Return the TickerPrice for a ticker, or None if not in cache."""
        return self._prices.get(ticker)

    def get_many(self, tickers: list[str]) -> list[TickerPrice]:
        """Return TickerPrice entries for all tickers present in the cache."""
        return [self._prices[t] for t in tickers if t in self._prices]

    def get_price(self, ticker: str) -> float | None:
        """Convenience: just the price float, or None if not in cache."""
        entry = self._prices.get(ticker)
        return entry.price if entry else None

    def all_tickers(self) -> list[str]:
        """Return all tickers currently in the cache."""
        return list(self._prices.keys())
