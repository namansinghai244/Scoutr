"""
main.py — Entry point for the Product Finder API.
Starts the FastAPI app and wires together all routes.
"""

from pathlib import Path
import logging

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from routes.chat import router as chat_router, limiter
from routes.health import router as health_router
from config import settings

logging.basicConfig(level=logging.INFO)

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_PATH = BASE_DIR / "index.html"
CORS_ALLOW_CREDENTIALS = "*" not in settings.ALLOWED_ORIGINS

# ── Create the FastAPI app ───────────────────────────────────────────────────
app = FastAPI(
    title="Scoutr Product Finder API",
    description="AI-powered product recommendation backend",
    version="1.0.0",
)

# ── Register rate limiter ────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS Middleware ──────────────────────────────────────────────────────────
# Allows your frontend (HTML file or hosted site) to call this backend.
# In production, replace "*" with your actual frontend domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register route modules ───────────────────────────────────────────────────
app.include_router(health_router)          # GET /health
app.include_router(chat_router, prefix="/api")  # POST /api/chat


# ── Serve frontend ───────────────────────────────────────────────────────────
@app.get("/")
async def serve_frontend():
    return FileResponse(FRONTEND_PATH)


# ── Run directly with: python main.py ───────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,   # Auto-restarts when you edit code (dev only)
    )
