"""Shared fixtures for LLM tests."""

import pytest

import db.connection as conn_module


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
