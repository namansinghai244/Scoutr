"""
services/image_service.py — Fetch real product images using DuckDuckGo search.
"""

import logging
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)

def fetch_product_image(search_query: str) -> str | None:
    """
    Fetches the top image URL for a given product search query using DDG.
    Falls back to None if no image is found or an error occurs.
    """
    try:
        logger.info(f"Fetching image for: {search_query}")
        with DDGS() as ddgs:
            results = list(ddgs.images(search_query, max_results=1))
            if results and len(results) > 0:
                image_url = results[0].get("image")
                logger.info(f"Found image URL: {image_url}")
                return image_url
    except Exception as e:
        logger.warning(f"Failed to fetch image for {search_query}: {e}")
        return None
    return None
