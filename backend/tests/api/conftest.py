"""Shared fixtures for API tests.

Provides an httpx AsyncClient against the FastAPI app with:
- Isolated temporary database per test
- Market simulator started (prices in cache)
"""

import asyncio

import httpx
import pytest

import db.connection as conn_module
from main import app, cache, provider


@pytest.fixture(autouse=True)
def isolated_db(tmp_path):
    """Use a fresh temporary database for every test."""
    db_path = str(tmp_path / "test.db")
    original = conn_module.DB_PATH
    conn_module.DB_PATH = db_path
    conn_module.reset_initialization()
    yield db_path
    conn_module.DB_PATH = original
    conn_module.reset_initialization()


@pytest.fixture()
async def seed_db():
    """Ensure the DB is initialized with seed data."""
    conn = await conn_module.get_connection()
    await conn.close()


@pytest.fixture()
async def seed_prices():
    """Start the market simulator briefly to populate PriceCache."""
    await provider.start()
    # Give the simulator one tick to populate prices
    await asyncio.sleep(0.6)
    yield cache
    await provider.stop()


@pytest.fixture()
async def client(seed_db, seed_prices):
    """Async httpx test client against the FastAPI app."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
