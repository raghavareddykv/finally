"""Pydantic models for LLM structured output."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class TradeAction(BaseModel):
    """A trade the LLM wants to execute."""

    ticker: str
    side: Literal["buy", "sell"]
    quantity: float


class WatchlistChange(BaseModel):
    """A watchlist modification the LLM wants to make."""

    ticker: str
    action: Literal["add", "remove"]


class LLMResponse(BaseModel):
    """Structured response from the LLM."""

    message: str
    trades: list[TradeAction] = []
    watchlist_changes: list[WatchlistChange] = []
