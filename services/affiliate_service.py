"""
services/affiliate_service.py — Builds monetised product links.
Uses ASIN for direct Amazon product pages when available.
Falls back to search URL if ASIN is not provided.
"""

from urllib.parse import urlencode, quote_plus
from config import settings


def build_amazon_link(search_query: str, asin: str = None) -> str:
    """
    Direct Amazon product page if ASIN provided (higher conversion).
    Falls back to search URL if no ASIN.
    """
    tag = settings.AMAZON_AFFILIATE_TAG
    if asin and asin.strip():
        return f"https://www.amazon.com/dp/{asin.strip()}?tag={tag}"
    params = {"k": search_query, "tag": tag}
    return f"https://www.amazon.com/s?{urlencode(params)}"


def build_google_shopping_link(search_query: str) -> str:
    return f"https://www.google.com/search?q={quote_plus(search_query)}&tbm=shop"


def build_ebay_link(search_query: str) -> str:
    return f"https://www.ebay.com/sch/i.html?_nkw={quote_plus(search_query)}"


def build_walmart_link(search_query: str) -> str:
    return f"https://www.walmart.com/search?q={quote_plus(search_query)}"


def build_all_links(search_query: str, asin: str = None) -> dict:
    return {
        "amazon": build_amazon_link(search_query, asin),
        "google": build_google_shopping_link(search_query),
        "ebay": build_ebay_link(search_query),
        "walmart": build_walmart_link(search_query),
    }
