"""Chat API endpoint — POST /api/chat."""

from fastapi import APIRouter

from llm.service import handle_chat_message
from market.cache import PriceCache


def create_chat_router(cache: PriceCache) -> APIRouter:
    """Create the chat router with injected PriceCache."""
    router = APIRouter(prefix="/api", tags=["chat"])

    @router.post("/chat")
    async def chat(body: dict):
        message = body.get("message", "").strip()
        if not message:
            return {"error": "Message is required", "code": "INVALID_REQUEST"}

        result = await handle_chat_message(
            user_message=message,
            price_cache=cache,
        )
        return result

    return router
