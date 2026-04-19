"""
models.py — Data shapes for every API request and response.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal


class MessageTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=3, max_length=1000)
    history: List[MessageTurn] = Field(default_factory=list)


class ProductLinks(BaseModel):
    amazon: str
    google: str
    ebay: Optional[str] = None
    walmart: Optional[str] = None


class ProductRecommendation(BaseModel):
    name: str
    category: str
    tagline: str
    estimated_price: str
    key_specs: List[str]
    why: str
    search_query: str
    asin: Optional[str] = None
    image_url: Optional[str] = None
    links: ProductLinks


class ChatResponse(BaseModel):
    intro: str
    budget: ProductRecommendation
    mid: ProductRecommendation
    premium: ProductRecommendation
    success: bool = True


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    detail: Optional[str] = None
