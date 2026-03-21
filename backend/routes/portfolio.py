"""Portfolio API endpoints — positions, trading, and history."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from db.crud import (
    create_portfolio_snapshot,
    create_trade,
    get_cash_balance,
    get_portfolio_snapshots,
    get_position,
    get_positions,
    update_cash_balance,
    upsert_position,
)
from market.cache import PriceCache
from market.tickers import SUPPORTED_TICKERS

MIN_QUANTITY = 0.001


def create_portfolio_router(cache: PriceCache) -> APIRouter:
    """Create the portfolio router with injected PriceCache."""
    router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

    @router.get("")
    async def get_portfolio():
        cash = await get_cash_balance()
        positions = await get_positions()

        enriched_positions = []
        positions_value = 0.0

        for pos in positions:
            ticker = pos["ticker"]
            current_price = cache.get_price(ticker)
            if current_price is None:
                current_price = pos["avg_cost"]

            market_value = pos["quantity"] * current_price
            cost_basis = pos["quantity"] * pos["avg_cost"]
            unrealized_pnl = market_value - cost_basis
            pnl_pct = (unrealized_pnl / cost_basis * 100) if cost_basis != 0 else 0.0
            positions_value += market_value

            enriched_positions.append({
                "ticker": ticker,
                "quantity": pos["quantity"],
                "avg_cost": round(pos["avg_cost"], 2),
                "current_price": round(current_price, 2),
                "market_value": round(market_value, 2),
                "unrealized_pnl": round(unrealized_pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
            })

        total_value = cash + positions_value

        return {
            "cash": round(cash, 2),
            "positions_value": round(positions_value, 2),
            "total_value": round(total_value, 2),
            "positions": enriched_positions,
        }

    @router.post("/trade")
    async def execute_trade(body: dict):
        ticker = body.get("ticker", "").upper().strip()
        side = body.get("side", "").lower().strip()
        quantity = body.get("quantity", 0)

        # Validate ticker
        if ticker not in SUPPORTED_TICKERS:
            return JSONResponse(
                status_code=400,
                content={"error": f"Ticker '{ticker}' is not in the supported universe", "code": "INVALID_TICKER"},
            )

        # Validate quantity
        try:
            quantity = float(quantity)
        except (TypeError, ValueError):
            return JSONResponse(
                status_code=400,
                content={"error": "Quantity must be a number", "code": "BELOW_MINIMUM_QUANTITY"},
            )

        if quantity < MIN_QUANTITY:
            return JSONResponse(
                status_code=400,
                content={"error": f"Minimum trade quantity is {MIN_QUANTITY}", "code": "BELOW_MINIMUM_QUANTITY"},
            )

        # Validate side
        if side not in ("buy", "sell"):
            return JSONResponse(
                status_code=400,
                content={"error": "Side must be 'buy' or 'sell'", "code": "INVALID_TICKER"},
            )

        # Get current price from cache
        current_price = cache.get_price(ticker)
        if current_price is None:
            return JSONResponse(
                status_code=400,
                content={"error": f"No price available for '{ticker}'", "code": "INVALID_TICKER"},
            )

        total_cost = current_price * quantity
        cash = await get_cash_balance()

        if side == "buy":
            if total_cost > cash:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": f"Insufficient cash. Need ${total_cost:.2f}, have ${cash:.2f}",
                        "code": "INSUFFICIENT_CASH",
                    },
                )

            # Update cash
            await update_cash_balance(cash - total_cost)

            # Update position (weighted average cost)
            existing = await get_position(ticker)
            if existing:
                old_qty = existing["quantity"]
                old_cost = existing["avg_cost"]
                new_qty = old_qty + quantity
                new_avg_cost = (old_qty * old_cost + quantity * current_price) / new_qty
            else:
                new_qty = quantity
                new_avg_cost = current_price

            await upsert_position(ticker, new_qty, new_avg_cost)

        else:  # sell
            existing = await get_position(ticker)
            if not existing or existing["quantity"] < quantity:
                held = existing["quantity"] if existing else 0
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": f"Insufficient shares. Trying to sell {quantity}, hold {held}",
                        "code": "INSUFFICIENT_SHARES",
                    },
                )

            # Update cash
            await update_cash_balance(cash + total_cost)

            # Update position
            new_qty = existing["quantity"] - quantity
            await upsert_position(ticker, new_qty, existing["avg_cost"])

        # Record the trade
        trade = await create_trade(ticker, side, quantity, current_price)

        # Take a portfolio snapshot after the trade
        new_cash = await get_cash_balance()
        positions = await get_positions()
        total_value = new_cash
        for pos in positions:
            p = cache.get_price(pos["ticker"])
            price = p if p is not None else pos["avg_cost"]
            total_value += pos["quantity"] * price
        await create_portfolio_snapshot(round(total_value, 2))

        return {
            "trade": trade,
            "cash": round(new_cash, 2),
            "total_value": round(total_value, 2),
        }

    @router.get("/history")
    async def portfolio_history():
        snapshots = await get_portfolio_snapshots()
        return snapshots

    return router
