"""
routes/health.py — GET /health
A lightweight endpoint used by hosting platforms (Railway, Render, etc.)
to check if your server is alive. Returns instantly with no database hit.
"""

from fastapi import APIRouter
from datetime import datetime, timezone

router = APIRouter()


@router.get("/health", tags=["Infrastructure"])
async def health_check():
    """
    Returns 200 OK if the server is running.
    Hosting platforms ping this every ~30 seconds to monitor uptime.
    """
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "fixr-product-finder-api",
    }
