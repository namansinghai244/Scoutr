"""
routes/chat.py — POST /api/chat
The only endpoint the frontend calls. Orchestrates the full flow:
  1. Validate the incoming message
  2. Ask Claude for a product recommendation
  3. Build affiliate links
  4. Return the structured response
"""

import logging
from fastapi import APIRouter, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from models import ChatRequest, ChatResponse, ProductRecommendation, ProductLinks
from services.ai_service import get_product_recommendation
from services.affiliate_service import build_all_links
from config import settings

logger = logging.getLogger(__name__)

# ── Rate limiter — protects your Anthropic bill ──────────────────────────────
limiter = Limiter(key_func=get_remote_address)

router = APIRouter()


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Get a product recommendation for a user problem",
    responses={
        200: {"description": "Successful recommendation"},
        422: {"description": "Validation error (message too short/long)"},
        429: {"description": "Too many requests"},
        500: {"description": "AI or server error"},
    },
)
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def chat(request: Request, body: ChatRequest):
    """
    Accepts a user problem description and returns a product recommendation
    with affiliate-tagged purchase links.

    Flow:
        Frontend → POST /api/chat { "message": "..." }
                → Claude API (ai_service.py)
                → Affiliate links (affiliate_service.py)
                → Response JSON back to frontend
    """
    logger.info(f"Chat request received: '{body.message[:60]}...'")

    # ── Step 1: Get recommendation from Claude ────────────────────────────
    try:
        history = [t.model_dump() for t in body.history]
        ai_data = await get_product_recommendation(body.message, history)
    except ValueError as e:
        # Model returned something we couldn't parse
        logger.error(f"AI parse error: {e}")
        raise HTTPException(status_code=500, detail="AI returned an unexpected format.")
    except Exception as e:
        # AI API error (network, auth, quota, etc.)
        logger.error(f"AI Service API error: {e}")
        raise HTTPException(status_code=502, detail="Could not reach AI service.")

    # ── Step 2: Build affiliate links from the search query ───────────────
    search_query = ai_data["product"]["search_query"]
    links = build_all_links(search_query)

    # ── Step 3: Assemble the final response ───────────────────────────────
    product_data = ai_data["product"]

    response = ChatResponse(
        intro=ai_data["intro"],
        product=ProductRecommendation(
            name=product_data["name"],
            category=product_data["category"],
            why=product_data["why"],
            search_query=search_query,
            links=ProductLinks(
                amazon=links["amazon"],
                google=links["google"],
            ),
            also_consider=product_data.get("also_consider"),
        ),
    )

    logger.info(f"Recommended: {product_data['name']}")
    return response
