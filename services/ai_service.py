"""
services/ai_service.py — OpenRouter API integration.
Returns 4 tiers (cost_effective / basic / premium / lavish) with 3 products each.
"""

import json
import asyncio
import logging
from openai import AsyncOpenAI
from cachetools import TTLCache
from config import settings

logger = logging.getLogger(__name__)

_client = AsyncOpenAI(
    api_key=settings.OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
)

_recommendation_cache = TTLCache(maxsize=1000, ttl=3600)

SYSTEM_PROMPT = """You are Scoutr, a product intelligence engine.

When a user describes a problem, return FOUR tiers of product recommendations with THREE products per tier (12 products total). The tiers are:

TIERS:
- cost_effective: Best products under $50. Maximum value for minimum spend.
- basic: Best products $50-$150. Solid quality, great price-to-performance.
- premium: Best products $150-$400. Professional grade, best-in-class features.
- lavish: Best products $400+. Absolute top-tier, no compromises, luxury.

RULES FOR EACH PRODUCT:
1. NAME: Exact brand and model. Never generic names.
2. TAGLINE: One punchy sentence that sells the product.
3. ESTIMATED_PRICE: Current market/deal price. Format "$X" or "$X-$Y".
4. ORIGINAL_PRICE: The original MSRP/retail price before any deals. Format "$X". If same as estimated_price, set to null.
5. KEY_SPECS: Exactly 3 short spec strings, each under 8 words.
6. WHY: 2 sentences. Sentence 1 references user's problem. Sentence 2 names the key differentiator.
7. SEARCH_QUERY: Brand + model + one key spec for retail search.
8. ASIN: Amazon ASIN (10-char code starting with B). Set null if unsure.

TONE:
- intro: 1-2 sentences acknowledging the problem directly. No filler.
- No emojis. Be direct and confident.

OUTPUT FORMAT — respond ONLY with valid JSON, no markdown:
{
  "intro": "string",
  "cost_effective": [
    {"name":"string","category":"string","tagline":"string","estimated_price":"string","original_price":"string or null","key_specs":["s","s","s"],"why":"string","search_query":"string","asin":"string or null"},
    {"name":"string","category":"string","tagline":"string","estimated_price":"string","original_price":"string or null","key_specs":["s","s","s"],"why":"string","search_query":"string","asin":"string or null"},
    {"name":"string","category":"string","tagline":"string","estimated_price":"string","original_price":"string or null","key_specs":["s","s","s"],"why":"string","search_query":"string","asin":"string or null"}
  ],
  "basic": [ ... same 3-product structure ... ],
  "premium": [ ... same 3-product structure ... ],
  "lavish": [ ... same 3-product structure ... ]
}"""

TIERS = ["cost_effective", "basic", "premium", "lavish"]
REQUIRED_KEYS = ["name", "category", "tagline", "estimated_price", "key_specs", "why", "search_query"]


async def get_product_recommendation(user_message: str, history: list | None = None) -> dict:
    max_retries = 3
    last_error = None
    raw_text = ""

    history = history or []
    trimmed_history = history[-6:]

    cache_key = f"{user_message}|{json.dumps(trimmed_history)}"
    if cache_key in _recommendation_cache:
        logger.info(f"Cache hit: '{user_message[:40]}'")
        return _recommendation_cache[cache_key]

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"OpenRouter attempt {attempt}/{max_retries}")

            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            for turn in trimmed_history:
                messages.append({"role": turn["role"], "content": turn["content"]})
            messages.append({"role": "user", "content": user_message})

            response = await _client.chat.completions.create(
                model=settings.OPENROUTER_MODEL,
                max_tokens=3000,
                messages=messages,
            )

            raw_text = response.choices[0].message.content
            if not raw_text:
                raise ValueError("Model returned empty response")

            raw_text = raw_text.strip()
            logger.info(f"Raw: {raw_text[:150]}")

            start = raw_text.find("{")
            end = raw_text.rfind("}")
            clean_json = raw_text[start:end + 1] if start != -1 and end > start else raw_text
            data = json.loads(clean_json)

            if "intro" not in data:
                raise ValueError(f"Missing 'intro'. Keys: {list(data.keys())}")

            for tier in TIERS:
                if tier not in data:
                    raise ValueError(f"Missing tier '{tier}'")
                products = data[tier]
                if not isinstance(products, list):
                    raise ValueError(f"Tier '{tier}' is not a list")
                if len(products) < 1:
                    raise ValueError(f"Tier '{tier}' has no products")
                # Pad to 3 if LLM returned fewer
                while len(products) < 3:
                    products.append(dict(products[0]))
                # Trim to 3
                data[tier] = products[:3]
                for i, p in enumerate(data[tier]):
                    for key in REQUIRED_KEYS:
                        if key not in p:
                            raise ValueError(f"Missing '{key}' in {tier}[{i}]")
                    if not isinstance(p.get("key_specs"), list):
                        p["key_specs"] = ["—", "—", "—"]
                    while len(p["key_specs"]) < 3:
                        p["key_specs"].append("—")
                    p.setdefault("asin", None)
                    p.setdefault("original_price", None)
                    p.setdefault("image_url", None)
                    logger.info(f"  {tier}[{i}]: {p['name']} {p['estimated_price']}")

            _recommendation_cache[cache_key] = data
            return data

        except json.JSONDecodeError as e:
            last_error = ValueError(f"JSON error (attempt {attempt}): {e} | {raw_text[:200]}")
            logger.warning(str(last_error))
        except ValueError as e:
            last_error = e
            logger.warning(f"Validation error (attempt {attempt}): {e}")
        except Exception as e:
            last_error = e
            logger.warning(f"API error (attempt {attempt}): {type(e).__name__}: {e}")

        if attempt < max_retries:
            wait = 3 * attempt
            logger.info(f"Retrying in {wait}s...")
            await asyncio.sleep(wait)

    raise last_error or Exception("All retries failed")
