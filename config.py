"""
config.py — Central configuration using environment variables.
Load secrets from a .env file (never hardcode API keys in source code).
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    # ── OpenRouter ────────────────────────────────────────────────────────────
    OPENROUTER_API_KEY: str = "your_openrouter_api_key_here"
    OPENROUTER_MODEL: str = "google/gemma-4-31b-it:free"
    OPENROUTER_MAX_TOKENS: int = 1024

    # ── Amazon Affiliate ─────────────────────────────────────────────────────
    # Get this after joining Amazon Associates: amazon.com/associates
    AMAZON_AFFILIATE_TAG: str = "your-tag-20"

    # ── Server ───────────────────────────────────────────────────────────────
    # In production: replace "*" with "https://yourfrontend.com"
    ALLOWED_ORIGINS: List[str] = ["*"]

    # ── Rate limiting ────────────────────────────────────────────────────────
    # Max requests per IP per minute (protects your API bill)
    RATE_LIMIT_PER_MINUTE: int = 10

    model_config = SettingsConfigDict(
        # Reads from a .env file in the project root
        env_file=".env",
        env_file_encoding="utf-8",
    )


# Single shared settings instance — import this everywhere
settings = Settings()
