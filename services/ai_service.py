"""
services/ai_service.py — All communication with OpenRouter API.
Uses the OpenAI SDK pointed at OpenRouter's endpoint.
Includes retry logic with exponential backoff for transient failures.
"""

import json
import asyncio
import logging
from openai import AsyncOpenAI
from config import settings

logger = logging.getLogger(__name__)

# ── Async OpenAI client pointed at OpenRouter ────────────────────────────────
# Must use AsyncOpenAI (not OpenAI) inside async FastAPI routes
_client = AsyncOpenAI(
    api_key=settings.OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
)

# ── System prompt — forces Claude to return strict JSON ──────────────────────
SYSTEM_PROMPT = """You are Fixr, a world-class product recommendation assistant.
A user will describe a problem they have. Your job is to recommend the single best
product that solves it, then explain exactly why.

RULES:
1. Be specific — include brand AND model name when possible (e.g. "Logitech MX Master 3S", not just "a mouse").
2. Prioritise value — don't always pick the most expensive option.
3. The "why" field MUST directly reference the user's stated problem.
4. Keep "intro" conversational, warm, and under 2 sentences.
5. "search_query" must be a clean Amazon search string (no special characters).
6. "also_consider" is ONE alternative product name only — no explanation needed.

YOU MUST RESPOND ONLY WITH VALID JSON. No markdown, no backticks, no explanation, no extra text before or after.
Use this exact schema:
{
  "intro": "string",
  "product": {
    "name": "string",
    "category": "string",
    "why": "string",
    "search_query": "string",
    "also_consider": "string or null"
  }
}"""


async def get_product_recommendation(user_message: str) -> dict:
    """
    Sends the user's problem to OpenRouter (Gemma model) and returns parsed dict.
    Retries up to 3 times with exponential backoff on failure.

    Args:
        user_message: The raw problem text typed by the user.

    Returns:
        A dict matching the JSON schema above.

    Raises:
        ValueError: If the model returns unparseable JSON after all retries.
        Exception: If the API call fails after all retries.
    """
    max_retries = 3
    delay = 5  # seconds — doubles each retry (5s → 10s → 20s)

    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"OpenRouter request attempt {attempt}/{max_retries}")

            response = await _client.chat.completions.create(
                model=settings.OPENROUTER_MODEL,
                max_tokens=settings.OPENROUTER_MAX_TOKENS,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": user_message},
                ],
            )

            # Extract raw text from the response
            raw_text = response.choices[0].message.content.strip()
            logger.info(f"Raw response received: {raw_text[:100]}...")

            # Strip accidental markdown fences if the model adds them
            if raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]
            raw_text = raw_text.strip()

            # Parse JSON
            data = json.loads(raw_text)

            # Basic validation — make sure required keys exist
            if "intro" not in data or "product" not in data:
                raise ValueError(f"Missing required keys in response: {data}")

            product = data["product"]
            required_product_keys = ["name", "category", "why", "search_query"]
            for key in required_product_keys:
                if key not in product:
                    raise ValueError(f"Missing product key '{key}' in: {product}")

            logger.info(f"Successfully parsed recommendation: {product['name']}")
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
