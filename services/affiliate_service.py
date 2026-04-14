"""
services/affiliate_service.py — Builds monetised product links.
Every link that goes back to the frontend passes through here so you
have one place to swap affiliate programmes or add tracking.
"""

from urllib.parse import urlencode, quote_plus
from config import settings


def build_amazon_link(search_query: str) -> str:
    """
    Builds an Amazon search URL with your affiliate tag appended.
    When a user clicks this and buys ANYTHING on Amazon within 24 hours,
    you earn a commission (typically 1–10% depending on category).

    Args:
        search_query: Plain text product name, e.g. "Logitech MX Master 3S mouse"

    Returns:
        Full URL, e.g.:
        https://www.amazon.com/s?k=Logitech+MX+Master+3S&tag=yourtag-20
    """
    params = {
        "k": search_query,
        "tag": settings.AMAZON_AFFILIATE_TAG,
    }
    return f"https://www.amazon.com/s?{urlencode(params)}"


def build_google_shopping_link(search_query: str) -> str:
    """
    Builds a Google Shopping link as a fallback (no affiliate tag needed).
    Useful if the product isn't on Amazon.

    Args:
        search_query: Plain text product name.

    Returns:
        Full Google Shopping URL.
    """
    encoded = quote_plus(search_query)
    return f"https://www.google.com/search?q={encoded}&tbm=shop"


def build_all_links(search_query: str) -> dict:
    """
    Convenience wrapper — returns both links as a dict.
    Used by the chat route to attach links to each recommendation.

    Returns:
        { "amazon": "...", "google": "..." }
    """
    return {
        "amazon": build_amazon_link(search_query),
        "google": build_google_shopping_link(search_query),
    }
