#!/usr/bin/env python3
"""Market Data Demo — shows the simulator streaming live prices in the terminal.

Run from the project root:
    cd backend && uv run python ../planning/market_data_demo.py

Or:
    PYTHONPATH=backend python planning/market_data_demo.py
"""

import asyncio
import importlib.util
import sys
import os

# Import modules directly by file path to avoid loading market/__init__.py,
# which imports MassivePoller (requires httpx — an optional dependency).
_backend = os.path.join(os.path.dirname(__file__), "..", "backend")


def _load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_backend, path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_tickers_mod = _load("market.tickers", "market/tickers.py")
_cache_mod = _load("market.cache", "market/cache.py")
_sim_mod = _load("market.simulator", "market/simulator.py")

PriceCache = _cache_mod.PriceCache
MarketSimulator = _sim_mod.MarketSimulator

# Watchlist to display (subset of the 48 supported tickers)
WATCHLIST = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"]

# ANSI color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"

HEADER = f"""
{YELLOW}{'=' * 72}
  FinAlly — Market Data Simulator Demo
  Streaming live GBM-simulated prices (500ms updates)
{'=' * 72}{RESET}
"""


def format_price_line(ticker: str, price: float, prev_price: float, direction: str, seed: float) -> str:
    """Format a single ticker line with color-coded price movement."""
    change = price - prev_price
    change_pct = (change / prev_price * 100) if prev_price else 0.0
    total_change_pct = ((price - seed) / seed * 100) if seed else 0.0

    if direction == "up":
        arrow = f"{GREEN}\u25b2{RESET}"
        price_color = GREEN
    elif direction == "down":
        arrow = f"{RED}\u25bc{RESET}"
        price_color = RED
    else:
        arrow = f"{DIM}-{RESET}"
        price_color = DIM

    total_color = GREEN if total_change_pct >= 0 else RED

    return (
        f"  {BOLD}{ticker:<6}{RESET} "
        f"{price_color}${price:>10.2f}{RESET} "
        f"{arrow} {price_color}{change:>+7.2f} ({change_pct:>+5.2f}%){RESET} "
        f"{DIM}|{RESET} "
        f"from seed: {total_color}{total_change_pct:>+6.2f}%{RESET}"
    )


async def run_demo(duration: int = 30, interval: float = 1.0) -> None:
    """Run the market simulator and display streaming prices.

    Args:
        duration: How long to run the demo in seconds.
        interval: How often to refresh the display in seconds.
    """
    cache = PriceCache()
    simulator = MarketSimulator(cache)

    print(HEADER)
    print(f"  {CYAN}Watchlist:{RESET} {', '.join(WATCHLIST)}")
    print(f"  {CYAN}Duration:{RESET}  {duration}s")
    print(f"  {CYAN}Refresh:{RESET}   every {interval}s")
    print()

    # Grab seed prices for total-change display
    seeds = {t: _tickers_mod.SUPPORTED_TICKERS[t] for t in WATCHLIST}

    await simulator.start()

    try:
        ticks = 0
        while ticks < int(duration / interval):
            ticks += 1
            await asyncio.sleep(interval)

            # Clear previous output (move cursor up)
            if ticks > 1:
                print(f"\033[{len(WATCHLIST) + 3}A", end="")

            elapsed = ticks * interval
            print(f"  {DIM}[{elapsed:5.1f}s / {duration}s]{RESET}")
            print(f"  {BOLD}{'Ticker':<6} {'Price':>11} {'':>3} {'Change':>17}   {'From Seed':>12}{RESET}")
            print(f"  {DIM}{'-' * 62}{RESET}")

            for ticker in WATCHLIST:
                entry = cache.get(ticker)
                if entry:
                    print(format_price_line(ticker, entry.price, entry.previous_price, entry.direction, seeds[ticker]))
                else:
                    print(f"  {ticker:<6} {DIM}waiting...{RESET}")

    except KeyboardInterrupt:
        print(f"\n{YELLOW}Interrupted.{RESET}")
    finally:
        await simulator.stop()

    # Final summary
    print(f"\n{YELLOW}{'=' * 72}{RESET}")
    print(f"  {BOLD}Final Prices{RESET}")
    print(f"  {YELLOW}{'=' * 72}{RESET}")
    for ticker in WATCHLIST:
        entry = cache.get(ticker)
        if entry:
            total_pct = (entry.price - seeds[ticker]) / seeds[ticker] * 100
            color = GREEN if total_pct >= 0 else RED
            print(f"  {BOLD}{ticker:<6}{RESET} ${entry.price:>10.2f}  {color}{total_pct:>+6.2f}% from seed{RESET}")
    print()


if __name__ == "__main__":
    duration = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    asyncio.run(run_demo(duration=duration))
