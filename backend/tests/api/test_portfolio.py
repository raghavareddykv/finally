"""Tests for portfolio API endpoints."""

import pytest


@pytest.mark.asyncio
async def test_get_portfolio_initial(client):
    resp = await client.get("/api/portfolio")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cash"] == 10000.0
    assert data["positions_value"] == 0.0
    assert data["total_value"] == 10000.0
    assert data["positions"] == []


@pytest.mark.asyncio
async def test_buy_shares(client):
    resp = await client.post("/api/portfolio/trade", json={
        "ticker": "AAPL", "side": "buy", "quantity": 5,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["trade"]["ticker"] == "AAPL"
    assert data["trade"]["side"] == "buy"
    assert data["trade"]["quantity"] == 5
    assert data["cash"] < 10000.0

    # Verify position appears
    resp = await client.get("/api/portfolio")
    portfolio = resp.json()
    assert len(portfolio["positions"]) == 1
    pos = portfolio["positions"][0]
    assert pos["ticker"] == "AAPL"
    assert pos["quantity"] == 5


@pytest.mark.asyncio
async def test_sell_shares(client):
    # Buy first
    await client.post("/api/portfolio/trade", json={
        "ticker": "AAPL", "side": "buy", "quantity": 10,
    })
    # Sell half
    resp = await client.post("/api/portfolio/trade", json={
        "ticker": "AAPL", "side": "sell", "quantity": 5,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["trade"]["side"] == "sell"
    assert data["trade"]["quantity"] == 5

    # Verify position updated
    resp = await client.get("/api/portfolio")
    pos = resp.json()["positions"][0]
    assert pos["quantity"] == 5


@pytest.mark.asyncio
async def test_sell_all_removes_position(client):
    # Buy then sell all
    await client.post("/api/portfolio/trade", json={
        "ticker": "AAPL", "side": "buy", "quantity": 5,
    })
    await client.post("/api/portfolio/trade", json={
        "ticker": "AAPL", "side": "sell", "quantity": 5,
    })

    resp = await client.get("/api/portfolio")
    assert resp.json()["positions"] == []


@pytest.mark.asyncio
async def test_buy_insufficient_cash(client):
    resp = await client.post("/api/portfolio/trade", json={
        "ticker": "NVDA", "side": "buy", "quantity": 1000,
    })
    assert resp.status_code == 400
    assert resp.json()["code"] == "INSUFFICIENT_CASH"


@pytest.mark.asyncio
async def test_sell_insufficient_shares(client):
    resp = await client.post("/api/portfolio/trade", json={
        "ticker": "AAPL", "side": "sell", "quantity": 5,
    })
    assert resp.status_code == 400
    assert resp.json()["code"] == "INSUFFICIENT_SHARES"


@pytest.mark.asyncio
async def test_trade_invalid_ticker(client):
    resp = await client.post("/api/portfolio/trade", json={
        "ticker": "FAKE", "side": "buy", "quantity": 1,
    })
    assert resp.status_code == 400
    assert resp.json()["code"] == "INVALID_TICKER"


@pytest.mark.asyncio
async def test_trade_below_minimum_quantity(client):
    resp = await client.post("/api/portfolio/trade", json={
        "ticker": "AAPL", "side": "buy", "quantity": 0.0001,
    })
    assert resp.status_code == 400
    assert resp.json()["code"] == "BELOW_MINIMUM_QUANTITY"


@pytest.mark.asyncio
async def test_trade_creates_snapshot(client):
    await client.post("/api/portfolio/trade", json={
        "ticker": "AAPL", "side": "buy", "quantity": 1,
    })

    resp = await client.get("/api/portfolio/history")
    assert resp.status_code == 200
    snapshots = resp.json()
    assert len(snapshots) >= 1
    assert snapshots[-1]["total_value"] > 0


@pytest.mark.asyncio
async def test_portfolio_history_empty(client):
    resp = await client.get("/api/portfolio/history")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_weighted_average_cost(client):
    # Buy 5 at market price
    resp1 = await client.post("/api/portfolio/trade", json={
        "ticker": "AAPL", "side": "buy", "quantity": 5,
    })
    price1 = resp1.json()["trade"]["price"]

    # Buy 5 more (price may have shifted slightly)
    resp2 = await client.post("/api/portfolio/trade", json={
        "ticker": "AAPL", "side": "buy", "quantity": 5,
    })
    price2 = resp2.json()["trade"]["price"]

    # Check weighted avg cost
    resp = await client.get("/api/portfolio")
    pos = resp.json()["positions"][0]
    expected_avg = (5 * price1 + 5 * price2) / 10
    assert abs(pos["avg_cost"] - round(expected_avg, 2)) < 0.02
