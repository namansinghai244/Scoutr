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
from services.image_service import fetch_product_image
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

    # ── Step 2: Build affiliate links and fetch image ───────────────
    product_data = ai_data.get("product")
    tier_options = ai_data.get("tier_options")
    
    if product_data:
        sq = product_data["search_query"]
        lnks = build_all_links(sq)
        
        img_url = fetch_product_image(sq)
        
        prod_rec = ProductRecommendation(
            name=product_data["name"],
            category=product_data["category"],
            estimated_price=product_data["estimated_price"],
            why=product_data["why"],
            search_query=sq,
            image_url=img_url,
            links=ProductLinks(amazon=lnks["amazon"], google=lnks["google"])
        )
        rec_name = product_data["name"]
    else:
        prod_rec = None
        rec_name = "Conversational Reply / Options"

    # ── Step 3: Assemble the final response ───────────────────────────────
    response = ChatResponse(
        intro=ai_data["intro"],
        tier_options=tier_options,
        product=prod_rec,
    )

    logger.info(f"Recommended: {rec_name}")
    return response
