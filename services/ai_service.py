"""
services/ai_service.py — OpenRouter API integration.
Always returns 3 products (budget / mid / premium). No tier selection step.
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

SYSTEM_PROMPT = """You are Scoutr, a product intelligence engine specialising in home and office products.

When a user describes a problem, you immediately return three product recommendations: one budget pick, one mid-range pick, and one premium pick. You never ask the user to choose a budget first. You show all three instantly so they can compare and decide.

PRODUCT CATEGORIES YOU KNOW:
Ergonomic chairs, standing desks, monitor arms, monitors, webcams, ring lights, desk lamps, mechanical keyboards, mice, laptop stands, headphones, noise-cancelling earbuds, cable management, desk organisers, air purifiers, humidifiers, smart plugs, multi-port chargers, coffee warmers, desk mats, whiteboards, document scanners, and productivity tools.

PRICE TIERS:
- budget: Best product under $75. Prioritise value, real availability, and strong user reviews.
- mid: Best product $75-$200. The pick most people should buy. Optimal price-to-quality ratio.
- premium: Best product $200 or more. No compromises. What professionals and power users buy.

RULES FOR EACH PRODUCT:
1. NAME: Exact brand and model. Never generic names. Write "Logitech MX Master 3S" not "a wireless mouse".
2. TAGLINE: One short punchy sentence that sells the product. Direct. Confident. No emojis. Example: "The chair that eliminates lower back pain in the first week."
3. ESTIMATED_PRICE: Realistic current market price for that tier. Format as "$X" or "$X-$Y".
4. KEY_SPECS: Exactly 3 short spec strings. Each under 8 words. Focus on specs most relevant to the user's problem. Example: ["Adjustable lumbar support", "Breathable mesh back", "12-year warranty"].
5. WHY: Exactly 2 sentences. Sentence 1 directly references the user's stated problem. Sentence 2 names the single most compelling feature that sets this product apart.
6. SEARCH_QUERY: A high-intent retail search string. Brand + model + one key spec. Example: "Logitech MX Master 3S wireless mouse graphite".
7. ASIN: The Amazon Standard Identification Number for this exact product. A 10-character code starting with B, found in Amazon product URLs. Example: "B09HMKFDXC". If you are not certain of the exact ASIN, set it to null. Do not guess.

TONE:
- intro: 1-2 sentences. Acknowledge the problem directly. No filler phrases like "Great question" or "Happy to help".
- No emojis anywhere in any field.
- Be direct and confident. You are an expert. Do not hedge.

OUTPUT FORMAT:
Respond ONLY with valid JSON. No markdown. No backticks. No text before or after the JSON.

{
  "intro": "string",
  "budget": {
    "name": "string",
    "category": "string",
    "tagline": "string",
    "estimated_price": "string",
    "key_specs": ["string", "string", "string"],
    "why": "string",
    "search_query": "string",
    "asin": "string or null"
  },
  "mid": {
    "name": "string",
    "category": "string",
    "tagline": "string",
    "estimated_price": "string",
    "key_specs": ["string", "string", "string"],
    "why": "string",
    "search_query": "string",
    "asin": "string or null"
  },
  "premium": {
    "name": "string",
    "category": "string",
    "tagline": "string",
    "estimated_price": "string",
    "key_specs": ["string", "string", "string"],
    "why": "string",
    "search_query": "string",
    "asin": "string or null"
  }
}"""


async def get_product_recommendation(user_message: str, history: list | None = None) -> dict:
    """
    Returns 3 product picks (budget, mid, premium) for a user's problem.
    Retries up to 3 times with exponential backoff.
    """
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
                max_tokens=settings.OPENROUTER_MAX_TOKENS,
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

            for tier in ["budget", "mid", "premium"]:
                if tier not in data:
                    raise ValueError(f"Missing tier '{tier}'")
                p = data[tier]
                for key in ["name", "category", "tagline", "estimated_price", "key_specs", "why", "search_query"]:
                    if key not in p:
                        raise ValueError(f"Missing '{key}' in {tier}")
                if not isinstance(p.get("key_specs"), list):
                    p["key_specs"] = ["—", "—", "—"]
                while len(p["key_specs"]) < 3:
                    p["key_specs"].append("—")
                p.setdefault("asin", None)
                p.setdefault("image_url", None)
                logger.info(f"  {tier}: {p['name']} {p['estimated_price']}")

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
