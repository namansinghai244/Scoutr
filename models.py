"""
models.py — Data shapes for every API request and response.
FastAPI uses these to validate incoming JSON and document the API automatically.
"""

from pydantic import BaseModel, Field
from typing import Optional


# ── Incoming request from the frontend ──────────────────────────────────────

class ChatRequest(BaseModel):
    """
    What the frontend sends to POST /api/chat.
    Example JSON body:
        { "message": "My back hurts when I sit all day" }
    """
    message: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="The user's problem description",
        json_schema_extra={"example": "My back hurts when I work from home all day"},
    )


# ── Sub-models for the response ──────────────────────────────────────────────

class ProductLinks(BaseModel):
    """
    Affiliate and search links for the recommended product.
    """
    amazon: str = Field(description="Full Amazon search URL with affiliate tag")
    google: str = Field(description="Google Shopping search URL")


class ProductRecommendation(BaseModel):
    """
    The product the AI recommends.
    """
    name: str = Field(description="Brand + product name, e.g. 'Secretlab Titan Evo 2022'")
    category: str = Field(description="Product category, e.g. 'Ergonomic Chair'")
    why: str = Field(description="Why this solves the user's specific problem")
    search_query: str = Field(description="Optimised Amazon search string")
    links: ProductLinks
    also_consider: Optional[str] = Field(
        None, description="One alternative product worth mentioning"
    )


class ChatResponse(BaseModel):
    """
    Full response returned to the frontend.
    Example JSON:
    {
        "intro": "Sounds like a classic WFH posture issue...",
        "product": { ... },
        "success": true
    }
    """
    intro: str = Field(description="Empathetic 1-2 sentence opener from the AI")
    product: ProductRecommendation
    success: bool = True


class ErrorResponse(BaseModel):
    """
    Returned when something goes wrong.
    """
    success: bool = False
    error: str
    detail: Optional[str] = None
