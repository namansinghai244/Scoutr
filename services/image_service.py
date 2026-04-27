"""
services/image_service.py - Returns product image URLs.

Priority:
1. Database image URLs from the product dataset
2. No fallback network fetch; the frontend can render its own placeholder
"""


def fetch_product_image(search_query: str, db_image_url: str | None = None) -> str | None:
    """Returns a dataset image URL when one is available."""
    del search_query  # Kept for call-site compatibility.

    if not db_image_url:
        return None

    image_url = db_image_url.strip()
    if not image_url or image_url.lower() == "nan":
        return None

    return image_url
