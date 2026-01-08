"""Card-related Pydantic models."""

from decimal import Decimal

from pydantic import BaseModel, Field


class Card(BaseModel):
    """Basic card information for search results and lists."""

    id: int = Field(..., description="Odoo product ID")
    sku: str = Field(..., description="Product SKU (default_code)")
    name: str = Field(..., description="Card name")
    set_name: str | None = Field(None, description="Set name from category")
    quantity: int = Field(0, description="Current stock quantity")
    price: Decimal = Field(Decimal("0.00"), description="List price")
    has_image: bool = Field(False, description="Whether the card has an image")


class CardDetail(Card):
    """Detailed card information for modal view."""

    variant: str | None = Field(None, description="Card variant (reverse holo, etc.)")
    card_number: str | None = Field(None, description="Card number in set")
    rarity: str | None = Field(None, description="Card rarity")
    barcode: str | None = Field(None, description="Product barcode")
    image_url: str | None = Field(None, description="URL to fetch card image")


class CardSearchResult(BaseModel):
    """Search results response."""

    cards: list[Card] = Field(default_factory=list)
    total: int = Field(0, description="Total number of matching cards")
    query: str = Field("", description="Original search query")

