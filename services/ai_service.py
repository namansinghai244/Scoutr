"""
services/ai_service.py — All communication with OpenRouter API.
Uses the OpenAI SDK pointed at OpenRouter's endpoint.
Includes retry logic with exponential backoff for transient failures.
"""

import json
import asyncio
import logging
from openai import AsyncOpenAI
from cachetools import TTLCache
from config import settings

logger = logging.getLogger(__name__)

# ── Async OpenAI client pointed at OpenRouter ────────────────────────────────
# Must use AsyncOpenAI (not OpenAI) inside async FastAPI routes
_client = AsyncOpenAI(
    api_key=settings.OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
)

# ── Caching ────────────────────────────────────────────────────────────────
# Caches identical requests (e.g. example chips) for 1 hour to save API costs
_recommendation_cache = TTLCache(maxsize=1000, ttl=3600)

SYSTEM_PROMPT = """You are Scoutr, a world-class product recommendation assistant.
A user will describe a problem they have.

RULES:
1. If the user has NOT specified whether they want a "Budget Pick", "Top Pick", or "Premium Pick", you MUST ask them which they prefer. Set "product" to null and "tier_options" to ["Budget Pick", "Top Pick", "Premium Pick"].
2. If the user HAS specified a tier, or if they explicitly ask for a specific product, recommend ONE single product that matches their request.
3. Be specific — include brand AND model name when possible.
4. "estimated_price" should be a realistic string (e.g. "$50").
5. The "why" field MUST explain why it fits that specific tier and solves the problem.
6. Keep "intro" conversational, warm, and under 2 sentences.
7. "search_query" must be a clean Amazon search string (no special characters).
8. If you just need to chat or clarify (other than tier), set "product" to null and "tier_options" to null.

YOU MUST RESPOND ONLY WITH VALID JSON. No markdown, no backticks, no explanation, no extra text before or after.
Use exactly this schema:
{
  "intro": "string",
  "tier_options": ["Budget Pick", "Top Pick", "Premium Pick"] | null,
  "product": {
    "name": "string",
    "category": "string",
    "estimated_price": "string",
    "why": "string",
    "search_query": "string"
  } // OR null
}"""


async def get_product_recommendation(user_message: str, history: list | None = None) -> dict:
    """
    Sends the user's problem to OpenRouter and returns a parsed product recommendation.
    Accepts optional conversation history for multi-turn follow-up questions.
    Retries up to 3 times with exponential backoff on failure.

    Args:
        user_message: The raw problem text typed by the user.
        history:      Optional list of previous {role, content} dicts for context.

    Returns:
        A dict matching the JSON schema above.

    Raises:
        ValueError: If the model returns unparseable JSON after all retries.
        Exception: If the API call fails after all retries.
    """
    max_retries = 3
    delay = 3  # base seconds — scales as 3*attempt (3s → 6s → 9s)

    last_error = None

    # Build the messages array: system → history (last 6 turns) → new user message
    history = history or []
    trimmed_history = history[-6:]  # cap at 3 exchanges to stay within token budget

    # ── Check Cache First ─────────────────────────────────────────────────────
    cache_key = f"{user_message}|{json.dumps(trimmed_history)}"
    if cache_key in _recommendation_cache:
        logger.info(f"Serving cached recommendation for: {user_message[:30]}...")
        return _recommendation_cache[cache_key]

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"OpenRouter request attempt {attempt}/{max_retries}")

            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            for turn in trimmed_history:
                messages.append({"role": turn["role"], "content": turn["content"]})
            messages.append({"role": "user", "content": user_message})

            response = await _client.chat.completions.create(
                model=settings.OPENROUTER_MODEL,
                max_tokens=settings.OPENROUTER_MAX_TOKENS,
                messages=messages,
            )

            # Extract raw text from the response
            raw_text = response.choices[0].message.content.strip()
            logger.info(f"Raw response received: {raw_text[:100]}...")

            # Strip accidental markdown fences if the model adds them
            if raw_text.startswith("```"):
                # Remove opening fence (```json or just ```)
                raw_text = raw_text.split("\n", 1)[-1] if "\n" in raw_text else raw_text[3:]
                # Remove trailing fence if present
                if raw_text.rstrip().endswith("```"):
                    raw_text = raw_text.rstrip()[:-3]
            raw_text = raw_text.strip()

            # Parse JSON with bulletproof extraction
            start_idx = raw_text.find("{")
            end_idx = raw_text.rfind("}")
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                clean_json = raw_text[start_idx:end_idx+1]
            else:
                clean_json = raw_text
                
            data = json.loads(clean_json)

            # Basic validation — make sure required keys exist
            if "intro" not in data:
                raise ValueError(f"Missing required key 'intro' in response: {data}")

            product = data.get("product")
            if product is not None:
                required_product_keys = ["name", "category", "estimated_price", "why", "search_query"]
                for key in required_product_keys:
                    if key not in product:
                        raise ValueError(f"Missing product key '{key}'")
                logger.info(f"Successfully parsed single-tier recommendation")
            else:
                logger.info(f"Conversational reply without product: {data.get('intro', '')[:30]}")
            
            # Save to cache
            _recommendation_cache[cache_key] = data
            
            return data

        except json.JSONDecodeError as e:
            last_error = ValueError(f"Model returned invalid JSON on attempt {attempt}: {e}\nRaw: {raw_text}")
            logger.warning(str(last_error))

        except ValueError as e:
            last_error = e
            logger.warning(f"Validation error on attempt {attempt}: {e}")

        except Exception as e:
            last_error = e
            logger.warning(f"API error on attempt {attempt}: {e}")

        # Wait before retrying (exponential backoff)
        if attempt < max_retries:
            wait = 3 * attempt
            logger.info(f"Retrying in {wait}s...")
            await asyncio.sleep(wait)

    # All retries exhausted
    raise last_error or Exception("All retry attempts failed with unknown error")
