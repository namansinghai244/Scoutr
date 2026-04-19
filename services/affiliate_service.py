"""
services/affiliate_service.py — Builds monetised product links.

Link priority:
1. Geniuslink (if TSID configured) — auto-localizes to user's country
2. Direct affiliate links with tracking IDs
3. Plain search URLs (fallback if no tracking IDs set)
"""

from urllib.parse import urlencode, quote_plus
from config import settings


def _geniuslink_wrap(url: str) -> str:
    """
    If Geniuslink is configured, wraps any URL through their redirect
    for automatic geo-localization. Otherwise returns the URL as-is.
    """
    tsid = settings.GENIUSLINK_TSID
    if tsid:
        return f"https://geni.us/{quote_plus(url)}?tsid={tsid}"
    return url


def build_amazon_link(search_query: str, asin: str = None) -> str:
    """
    Direct product page if ASIN provided (higher conversion).
    Falls back to search URL. Wrapped through Geniuslink if configured.
    """
    tag = settings.AMAZON_AFFILIATE_TAG
    if asin and asin.strip():
        url = f"https://www.amazon.com/dp/{asin.strip()}?tag={tag}"
    else:
        url = f"https://www.amazon.com/s?{urlencode({'k': search_query, 'tag': tag})}"
    return _geniuslink_wrap(url)


def build_ebay_link(search_query: str) -> str:
    """eBay search with Partner Network tracking if campaign ID is set."""
    base = f"https://www.ebay.com/sch/i.html?_nkw={quote_plus(search_query)}"
    cid = settings.EBAY_CAMPAIGN_ID
    if cid:
        base += f"&mkcid=1&mkrid=711-53200-19255-0&campid={cid}"
    return base


def build_walmart_link(search_query: str) -> str:
    """Walmart search with Impact tracking if affiliate ID is set."""
    wid = settings.WALMART_IMPACT_ID
    if wid:
        dest = quote_plus(f"https://www.walmart.com/search?q={quote_plus(search_query)}")
        return f"https://goto.walmart.com/c/{wid}/568844/9383?veh=aff&sourceid=imp&u={dest}"
    return f"https://www.walmart.com/search?q={quote_plus(search_query)}"


def build_google_shopping_link(search_query: str) -> str:
    return f"https://www.google.com/search?q={quote_plus(search_query)}&tbm=shop"


def build_all_links(search_query: str, asin: str = None) -> dict:
    """Returns all affiliate links for a product. Used by chat route."""
    return {
        "amazon": build_amazon_link(search_query, asin),
        "google": build_google_shopping_link(search_query),
        "ebay": build_ebay_link(search_query),
        "walmart": build_walmart_link(search_query),
    }
