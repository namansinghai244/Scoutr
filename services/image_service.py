"""
services/image_service.py — Returns product image URLs.

Priority:
1. Database image URLs from the product dataset
2. DuckDuckGo image search fallback
"""

import logging

try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None

logger = logging.getLogger(__name__)


def fetch_product_image(search_query: str, db_image_url: str | None = None) -> str | None:
    """Returns a product image URL, preferring the dataset image when available."""
    if db_image_url and db_image_url.strip() and db_image_url.strip().lower() != "nan":
        return db_image_url.strip()

    if DDGS is None:
        return None

    try:
        logger.info(f"Fetching fallback image for: {search_query}")
        with DDGS() as ddgs:
            results = list(ddgs.images(search_query, max_results=1))
            if results:
                image_url = results[0].get("image")
                logger.info(f"Found fallback image URL: {image_url}")
                return image_url
    except Exception as exc:
        logger.warning(f"Failed to fetch image for {search_query}: {exc}")
    return None
