"""
routes/chat.py — POST /api/chat
Returns 4 tiers (cost_effective, basic, premium, lavish) with 3 products each.
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
limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

TIERS = ["cost_effective", "basic", "premium", "lavish"]


def build_product(product_data: dict) -> ProductRecommendation:
    sq = product_data["search_query"]
    asin = product_data.get("asin")
    links = build_all_links(sq, asin)
    image_url = fetch_product_image(sq)
    return ProductRecommendation(
        name=product_data["name"],
        category=product_data["category"],
        tagline=product_data["tagline"],
        estimated_price=product_data["estimated_price"],
        original_price=product_data.get("original_price"),
        key_specs=product_data["key_specs"],
        why=product_data["why"],
        search_query=sq,
        asin=asin,
        image_url=image_url,
        links=ProductLinks(
            amazon=links["amazon"],
            google=links["google"],
            ebay=links["ebay"],
            walmart=links["walmart"],
        ),
    )


@router.post("/chat", response_model=ChatResponse)
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def chat(request: Request, body: ChatRequest):
    logger.info(f"Request: '{body.message[:60]}'")

    try:
        history = [t.model_dump() for t in body.history]
        ai_data = await get_product_recommendation(body.message, history)
    except ValueError as e:
        logger.error(f"AI parse error: {e}")
        raise HTTPException(status_code=500, detail="AI returned an unexpected format. Please try again.")
    except Exception as e:
        logger.error(f"AI service error: {e}")
        raise HTTPException(status_code=502, detail="Could not reach AI service. Please try again.")

    try:
        result = {"intro": ai_data["intro"]}
        for tier in TIERS:
            products = ai_data[tier]
            result[tier] = [build_product(p) for p in products]
            names = [p["name"] for p in products]
            logger.info(f"  {tier}: {', '.join(names)}")
    except Exception as e:
        logger.error(f"Product build error: {e}")
        raise HTTPException(status_code=500, detail="Failed to assemble product data.")

    return ChatResponse(**result)
