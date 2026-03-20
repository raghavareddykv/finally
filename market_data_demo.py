#!/usr/bin/env python3
"""Market Data Demo — Watch the simulator generate live prices.

Run from the project root:
    cd backend && uv run python ../market_data_demo.py

Or if you have the backend dependencies installed:
    python market_data_demo.py
"""

import asyncio
import sys
import os

# Add backend to path so we can import the market package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from market.cache import PriceCache
from market.simulator import MarketSimulator

# Tickers to display in the demo
DEMO_TICKERS = ["AAPL", "GOOGL", "TSLA", "NVDA", "MSFT", "AMZN", "META", "JPM", "KO", "V"]

# ANSI color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def clear_screen():
    print("\033[2J\033[H", end="")


def format_price_line(ticker: str, price: float, prev_price: float, direction: str, seed: float) -> str:
    """Format a single ticker line with color coding."""
    # Direction arrow and color
    if direction == "up":
        arrow = "▲"
        color = GREEN
    elif direction == "down":
        arrow = "▼"
        color = RED
    else:
        arrow = "─"
        color = DIM

    # Change from previous tick
    change = price - prev_price
    change_pct = (change / prev_price * 100) if prev_price > 0 else 0.0

    # Change from seed (session P&L)
    session_change = ((price - seed) / seed) * 100

    if session_change >= 0:
        session_color = GREEN
        session_sign = "+"
    else:
        session_color = RED
        session_sign = ""

    return (
        f"  {BOLD}{ticker:<6}{RESET} "
        f"{color}{arrow} ${price:>10.2f}{RESET}  "
        f"{color}{change:>+7.2f} ({change_pct:>+6.2f}%){RESET}  "
        f"{DIM}seed: ${seed:>8.2f}{RESET}  "
        f"{session_color}{session_sign}{session_change:.2f}%{RESET}"
    )


async def run_demo():
    """Run the market simulator and display live prices."""
    cache = PriceCache()
    sim = MarketSimulator(cache)

    print(f"\n{BOLD}{YELLOW}  FinAlly Market Data Simulator Demo{RESET}")
    print(f"{DIM}  Starting simulator...{RESET}\n")

    await sim.start()

    # Get seed prices for comparison
    from market.tickers import SUPPORTED_TICKERS
    seeds = {t: SUPPORTED_TICKERS[t] for t in DEMO_TICKERS}

    tick_count = 0
    try:
        while True:
            await asyncio.sleep(0.5)
            tick_count += 1

            clear_screen()

            print(f"\n{BOLD}{YELLOW}  FinAlly Market Data Simulator Demo{RESET}")
            print(f"{DIM}  Live prices updating every 500ms | Tick #{tick_count} | Press Ctrl+C to stop{RESET}")
            print()
            print(f"  {BOLD}{'TICKER':<6} {'':>3}{'PRICE':>10}  {'CHANGE':>7} {'':>9}  {'SEED':>13}  SESSION{RESET}")
            print(f"  {DIM}{'─' * 75}{RESET}")

            for ticker in DEMO_TICKERS:
                entry = cache.get(ticker)
                if entry:
                    line = format_price_line(
                        ticker, entry.price, entry.previous_price,
                        entry.direction, seeds[ticker]
                    )
                    print(line)

            print(f"\n  {DIM}Simulating {len(sim.get_supported_tickers())} tickers total "
                  f"(showing {len(DEMO_TICKERS)}){RESET}")
            print(f"  {DIM}Model: GBM with Ito correction + Merton jump-diffusion + soft mean reversion{RESET}")

            # Show a random "event" indicator
            all_prices = []
            for t in DEMO_TICKERS:
                e = cache.get(t)
                if e and abs(e.price - e.previous_price) / e.previous_price > 0.01:
                    all_prices.append(t)

            if all_prices:
                print(f"\n  {BOLD}{CYAN}Jump detected:{RESET} {', '.join(all_prices)}")

    except KeyboardInterrupt:
        print(f"\n\n{DIM}  Shutting down simulator...{RESET}")
    finally:
        await sim.stop()
        print(f"{DIM}  Done.{RESET}\n")


if __name__ == "__main__":
    asyncio.run(run_demo())
