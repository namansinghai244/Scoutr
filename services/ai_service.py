"""
services/ai_service.py — OpenRouter API integration.

Uses ProductDB-backed retrieval when dataset assets are available and
falls back to AI-only recommendations otherwise.
"""

import asyncio
import json
import logging
import re
from typing import Any

from cachetools import TTLCache
from openai import AsyncOpenAI

from config import settings

logger = logging.getLogger(__name__)

_client = AsyncOpenAI(
    api_key=settings.OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
)
_recommendation_cache = TTLCache(maxsize=1000, ttl=3600)

TIERS = ["cost_effective", "basic", "premium", "lavish"]
REQUIRED_KEYS = [
    "name",
    "category",
    "tagline",
    "estimated_price",
    "key_specs",
    "why",
    "search_query",
]
ASIN_PATTERN = re.compile(r"^B[A-Z0-9]{9}$")

SYSTEM_PROMPT_AI_ONLY = """You are Scoutr, a product intelligence engine.

Return FOUR tiers of product recommendations with THREE products per tier (12 total). The tiers are:
- cost_effective: under $50
- basic: $50-$150
- premium: $150-$400
- lavish: $400+

For each product:
1. NAME: Exact brand and model. Never generic names.
2. TAGLINE: One punchy sentence. No emojis.
3. ESTIMATED_PRICE: Current market price. Format "$X" or "$X-$Y".
4. ORIGINAL_PRICE: MSRP before deals. Null if the same as estimated_price.
5. KEY_SPECS: Exactly 3 short spec strings, each under 8 words.
6. WHY: Exactly 2 sentences. Sentence 1 references the user's problem. Sentence 2 names the key differentiator.
7. SEARCH_QUERY: Brand + model + one key spec.
8. ASIN: A real Amazon ASIN if certain, otherwise null. Do not guess.

TONE:
- intro is 1-2 direct sentences.
- No emojis anywhere.
- Be direct and confident.

Respond ONLY with valid JSON:
{
  "intro": "string",
  "cost_effective": [
    {"name":"string","category":"string","tagline":"string","estimated_price":"string","original_price":null,"key_specs":["string","string","string"],"why":"string","search_query":"string","asin":null},
    {"name":"string","category":"string","tagline":"string","estimated_price":"string","original_price":null,"key_specs":["string","string","string"],"why":"string","search_query":"string","asin":null},
    {"name":"string","category":"string","tagline":"string","estimated_price":"string","original_price":null,"key_specs":["string","string","string"],"why":"string","search_query":"string","asin":null}
  ],
  "basic": [
    {"name":"string","category":"string","tagline":"string","estimated_price":"string","original_price":null,"key_specs":["string","string","string"],"why":"string","search_query":"string","asin":null},
    {"name":"string","category":"string","tagline":"string","estimated_price":"string","original_price":null,"key_specs":["string","string","string"],"why":"string","search_query":"string","asin":null},
    {"name":"string","category":"string","tagline":"string","estimated_price":"string","original_price":null,"key_specs":["string","string","string"],"why":"string","search_query":"string","asin":null}
  ],
  "premium": [
    {"name":"string","category":"string","tagline":"string","estimated_price":"string","original_price":null,"key_specs":["string","string","string"],"why":"string","search_query":"string","asin":null},
    {"name":"string","category":"string","tagline":"string","estimated_price":"string","original_price":null,"key_specs":["string","string","string"],"why":"string","search_query":"string","asin":null},
    {"name":"string","category":"string","tagline":"string","estimated_price":"string","original_price":null,"key_specs":["string","string","string"],"why":"string","search_query":"string","asin":null}
  ],
  "lavish": [
    {"name":"string","category":"string","tagline":"string","estimated_price":"string","original_price":null,"key_specs":["string","string","string"],"why":"string","search_query":"string","asin":null},
    {"name":"string","category":"string","tagline":"string","estimated_price":"string","original_price":null,"key_specs":["string","string","string"],"why":"string","search_query":"string","asin":null},
    {"name":"string","category":"string","tagline":"string","estimated_price":"string","original_price":null,"key_specs":["string","string","string"],"why":"string","search_query":"string","asin":null}
  ]
}"""


def _format_price(value: Any, currency: str | None) -> str:
    if value in (None, "", "nan"):
        return "Unknown"
    try:
        amount = float(value)
        symbol = "$" if (currency or "").upper() == "USD" else "₹"
        if amount.is_integer():
            return f"{symbol}{int(amount)}"
        return f"{symbol}{amount:.2f}"
    except (TypeError, ValueError):
        return str(value)


def _normalize_asin(source_id: Any) -> str | None:
    if source_id is None:
        return None
    text = str(source_id).strip().upper()
    return text if ASIN_PATTERN.match(text) else None


def _normalize_db_product(product: dict) -> dict:
    discounted_price = product.get("discounted_price")
    actual_price = product.get("actual_price")
    currency = product.get("currency") or ("USD" if product.get("store") == "amazon" else "INR")
    return {
        "name": product.get("name") or "Unknown Product",
        "category": product.get("category") or product.get("sub_category") or "General",
        "estimated_price": _format_price(discounted_price or actual_price, currency),
        "original_price": (
            _format_price(actual_price, currency)
            if actual_price and discounted_price and str(actual_price) != str(discounted_price)
            else None
        ),
        "asin": _normalize_asin(product.get("source_id")),
        "image_url": product.get("image_url"),
        "description": str(product.get("description") or "")[:300],
        "rating": product.get("rating"),
        "store": product.get("store") or "amazon",
        "product_url": product.get("product_url"),
    }


def build_db_prompt(products_by_tier: dict[str, list[dict]], user_query: str) -> str:
    """Builds a prompt that asks the model to describe real DB-backed products."""
    normalized = {
        tier: [_normalize_db_product(product) for product in products]
        for tier, products in products_by_tier.items()
    }
    products_text = json.dumps(normalized, ensure_ascii=True, indent=2)

    return f"""You are Scoutr, a product intelligence engine.

The user problem is: "{user_query}"

Below are REAL products retrieved from our product database. Do not invent, rename, swap, or reorder products.
For each product:
1. Keep name, category, estimated_price, original_price, asin, and image_url exactly as given.
2. Write one punchy tagline.
3. Write exactly 3 short key specs using the description and product context.
4. Write exactly 2 sentences for why: sentence 1 references the user's problem, sentence 2 names the standout feature.
5. Write a search_query using brand/model/spec wording.

REAL PRODUCTS JSON:
{products_text}

Respond ONLY with valid JSON using this schema:
{{
  "intro": "string",
  "cost_effective": [
    {{"name":"string","category":"string","tagline":"string","estimated_price":"string","original_price":null,"key_specs":["string","string","string"],"why":"string","search_query":"string","asin":null,"image_url":null}},
    {{"name":"string","category":"string","tagline":"string","estimated_price":"string","original_price":null,"key_specs":["string","string","string"],"why":"string","search_query":"string","asin":null,"image_url":null}},
    {{"name":"string","category":"string","tagline":"string","estimated_price":"string","original_price":null,"key_specs":["string","string","string"],"why":"string","search_query":"string","asin":null,"image_url":null}}
  ],
  "basic": [
    {{"name":"string","category":"string","tagline":"string","estimated_price":"string","original_price":null,"key_specs":["string","string","string"],"why":"string","search_query":"string","asin":null,"image_url":null}},
    {{"name":"string","category":"string","tagline":"string","estimated_price":"string","original_price":null,"key_specs":["string","string","string"],"why":"string","search_query":"string","asin":null,"image_url":null}},
    {{"name":"string","category":"string","tagline":"string","estimated_price":"string","original_price":null,"key_specs":["string","string","string"],"why":"string","search_query":"string","asin":null,"image_url":null}}
  ],
  "premium": [
    {{"name":"string","category":"string","tagline":"string","estimated_price":"string","original_price":null,"key_specs":["string","string","string"],"why":"string","search_query":"string","asin":null,"image_url":null}},
    {{"name":"string","category":"string","tagline":"string","estimated_price":"string","original_price":null,"key_specs":["string","string","string"],"why":"string","search_query":"string","asin":null,"image_url":null}},
    {{"name":"string","category":"string","tagline":"string","estimated_price":"string","original_price":null,"key_specs":["string","string","string"],"why":"string","search_query":"string","asin":null,"image_url":null}}
  ],
  "lavish": [
    {{"name":"string","category":"string","tagline":"string","estimated_price":"string","original_price":null,"key_specs":["string","string","string"],"why":"string","search_query":"string","asin":null,"image_url":null}},
    {{"name":"string","category":"string","tagline":"string","estimated_price":"string","original_price":null,"key_specs":["string","string","string"],"why":"string","search_query":"string","asin":null,"image_url":null}},
    {{"name":"string","category":"string","tagline":"string","estimated_price":"string","original_price":null,"key_specs":["string","string","string"],"why":"string","search_query":"string","asin":null,"image_url":null}}
  ]
}}"""


def _validate_response(data: dict) -> dict:
    if "intro" not in data:
        raise ValueError(f"Missing 'intro'. Keys: {list(data.keys())}")

    for tier in TIERS:
        if tier not in data:
            raise ValueError(f"Missing tier '{tier}'")
        products = data[tier]
        if not isinstance(products, list):
            raise ValueError(f"Tier '{tier}' is not a list")
        if len(products) != 3:
            raise ValueError(f"Tier '{tier}' must contain exactly 3 products, got {len(products)}")

        for index, product in enumerate(products):
            for key in REQUIRED_KEYS:
                if key not in product:
                    raise ValueError(f"Missing '{key}' in {tier}[{index}]")
            if not isinstance(product.get("key_specs"), list):
                product["key_specs"] = ["-", "-", "-"]
            while len(product["key_specs"]) < 3:
                product["key_specs"].append("-")
            product["key_specs"] = product["key_specs"][:3]
            product.setdefault("original_price", None)
            product.setdefault("image_url", None)
            product["asin"] = _normalize_asin(product.get("asin"))
            logger.info(f"  {tier}[{index}]: {product['name']} {product['estimated_price']}")
    return data


async def _call_api(messages: list[dict], max_retries: int = 3) -> dict:
    last_error = None
    raw_text = ""

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"OpenRouter attempt {attempt}/{max_retries}")
            response = await _client.chat.completions.create(
                model=settings.OPENROUTER_MODEL,
                max_tokens=settings.OPENROUTER_MAX_TOKENS,
                messages=messages,
            )
            raw_text = (response.choices[0].message.content or "").strip()
            if not raw_text:
                raise ValueError("Model returned empty response")

            logger.info(f"Raw: {raw_text[:150]}")
            start = raw_text.find("{")
            end = raw_text.rfind("}")
            clean_json = raw_text[start : end + 1] if start != -1 and end > start else raw_text
            data = json.loads(clean_json)
            return _validate_response(data)
        except json.JSONDecodeError as exc:
            last_error = ValueError(f"JSON error (attempt {attempt}): {exc} | {raw_text[:200]}")
            logger.warning(str(last_error))
        except ValueError as exc:
            last_error = exc
            logger.warning(f"Validation error (attempt {attempt}): {exc}")
        except Exception as exc:
            last_error = exc
            logger.warning(f"API error (attempt {attempt}): {type(exc).__name__}: {exc}")

        if attempt < max_retries:
            wait = 3 * attempt
            logger.info(f"Retrying in {wait}s...")
            await asyncio.sleep(wait)

    raise last_error or Exception("All retries failed")


async def _ai_only_recommendation(user_message: str, history: list[dict], cache_key: str) -> dict:
    logger.info("AI-only mode")
    messages = [{"role": "system", "content": SYSTEM_PROMPT_AI_ONLY}]
    for turn in history:
        messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": user_message})

    data = await _call_api(messages)
    _recommendation_cache[cache_key] = data
    return data


async def _db_assisted_recommendation(
    user_message: str,
    history: list[dict],
    cache_key: str,
    db: Any,
) -> dict:
    logger.info("DB-assisted mode")
    products_by_tier = db.search_for_tiers(query=user_message)
    counts = {tier: len(products) for tier, products in products_by_tier.items()}
    logger.info(f"DB returned: {counts}")

    if any(len(products_by_tier.get(tier, [])) < 3 for tier in TIERS):
        raise ValueError("ProductDB did not return 3 products for every tier")

    prompt = build_db_prompt(products_by_tier, user_message)
    messages = [{"role": "system", "content": prompt}]
    for turn in history:
        messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": user_message})

    data = await _call_api(messages)
    _recommendation_cache[cache_key] = data
    return data


async def get_product_recommendation(user_message: str, history: list | None = None) -> dict:
    history = history or []
    trimmed_history = history[-6:]
    cache_key = f"{user_message}|{json.dumps(trimmed_history)}"

    if cache_key in _recommendation_cache:
        logger.info(f"Cache hit: '{user_message[:40]}'")
        return _recommendation_cache[cache_key]

    try:
        from services.db_service import get_db

        db = get_db()
        if db.is_ready:
            try:
                return await _db_assisted_recommendation(
                    user_message,
                    trimmed_history,
                    cache_key,
                    db,
                )
            except Exception as exc:
                logger.warning(f"DB-assisted mode failed: {exc}. Falling back to AI-only.")
    except Exception as exc:
        logger.warning(f"ProductDB unavailable: {exc}. Falling back to AI-only.")

    return await _ai_only_recommendation(user_message, trimmed_history, cache_key)
