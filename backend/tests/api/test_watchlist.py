"""Tests for watchlist API endpoints."""

import pytest


@pytest.mark.asyncio
async def test_list_default_watchlist(client):
    resp = await client.get("/api/watchlist")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 10
    tickers = {item["ticker"] for item in data}
    assert "AAPL" in tickers
    assert "GOOGL" in tickers
    # Each entry should have price data from the cache
    for item in data:
        assert item["price"] is not None
        assert item["ticker"] is not None


@pytest.mark.asyncio
async def test_add_valid_ticker(client):
    resp = await client.post("/api/watchlist", json={"ticker": "PYPL"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["ticker"] == "PYPL"
    assert data["price"] is not None


@pytest.mark.asyncio
async def test_add_invalid_ticker(client):
    resp = await client.post("/api/watchlist", json={"ticker": "FAKE"})
    assert resp.status_code == 400
    data = resp.json()
    assert data["code"] == "INVALID_TICKER"


@pytest.mark.asyncio
async def test_add_duplicate_ticker(client):
    resp = await client.post("/api/watchlist", json={"ticker": "AAPL"})
    assert resp.status_code == 409
    data = resp.json()
    assert data["code"] == "TICKER_ALREADY_WATCHED"


@pytest.mark.asyncio
async def test_remove_ticker(client):
    resp = await client.delete("/api/watchlist/AAPL")
    assert resp.status_code == 200
    data = resp.json()
    assert "Removed" in data["message"]

    # Verify it's gone
    resp = await client.get("/api/watchlist")
    tickers = {item["ticker"] for item in resp.json()}
    assert "AAPL" not in tickers


@pytest.mark.asyncio
async def test_remove_nonexistent_ticker(client):
    resp = await client.delete("/api/watchlist/PYPL")
    assert resp.status_code == 404
    assert resp.json()["code"] == "TICKER_NOT_FOUND"


@pytest.mark.asyncio
async def test_remove_ticker_with_position_blocked(client):
    # Buy some AAPL first
    await client.post("/api/portfolio/trade", json={
        "ticker": "AAPL", "side": "buy", "quantity": 1,
    })

    # Try to remove it from watchlist
    resp = await client.delete("/api/watchlist/AAPL")
    assert resp.status_code == 409
    assert resp.json()["code"] == "POSITION_EXISTS"
