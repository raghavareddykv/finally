"""Health check endpoint."""

from fastapi import APIRouter

router = APIRouter(tags=["system"])


@router.get("/api/health")
async def health_check():
    return {"status": "ok"}
