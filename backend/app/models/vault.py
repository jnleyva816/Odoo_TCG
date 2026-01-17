"""Digital Vault models for public collection showcase."""

from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class VaultVisibility(str, Enum):
    """Vault visibility settings."""

    PRIVATE = "private"  # Only owner can see
    UNLISTED = "unlisted"  # Anyone with link can see
    PUBLIC = "public"  # Listed in public directory


class VaultCard(BaseModel):
    """A card in a public vault."""

    product_id: int
    name: str
    sku: str
    set_name: str
    set_code: str
    rarity: str | None = None
    image_url: str | None = None
    quantity: int = 1
    price: Decimal | None = None  # Optional - owner can hide prices
    condition: str | None = None  # NM, LP, MP, HP, DMG
    notes: str | None = None  # Seller notes


class VaultSettings(BaseModel):
    """Settings for a vault/binder."""

    show_prices: bool = True
    show_quantities: bool = True
    allow_offers: bool = False
    contact_method: str | None = None  # Discord, email, etc.
    custom_message: str | None = None  # "DM me on Discord for trades!"


class Vault(BaseModel):
    """A published collection binder."""

    id: str  # Short unique ID (e.g., "xyz123")
    owner_id: int  # Odoo user ID
    owner_name: str  # Display name
    name: str  # "High-End Trades", "PSA Graded", etc.
    description: str | None = None
    visibility: VaultVisibility = VaultVisibility.UNLISTED
    settings: VaultSettings = Field(default_factory=VaultSettings)

    # Stats
    card_count: int = 0
    total_value: Decimal | None = None  # Only shown if show_prices=True
    view_count: int = 0

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    published_at: datetime | None = None

    # CDN/Cache info
    static_url: str | None = None  # CDN URL for static JSON
    cache_key: str | None = None  # Redis cache key


class VaultCreate(BaseModel):
    """Input for creating a new vault."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    visibility: VaultVisibility = VaultVisibility.UNLISTED
    settings: VaultSettings = Field(default_factory=VaultSettings)
    product_ids: list[int] = Field(default_factory=list)  # Cards to include


class VaultUpdate(BaseModel):
    """Input for updating a vault."""

    name: str | None = None
    description: str | None = None
    visibility: VaultVisibility | None = None
    settings: VaultSettings | None = None
    product_ids: list[int] | None = None  # Replace card list


class VaultPublic(BaseModel):
    """Public view of a vault (for sharing)."""

    id: str
    owner_name: str
    name: str
    description: str | None = None
    cards: list[VaultCard] = Field(default_factory=list)
    card_count: int = 0
    total_value: Decimal | None = None
    settings: VaultSettings
    published_at: datetime | None = None

    # For filtering/searching in frontend
    sets: list[str] = Field(default_factory=list)  # Unique set names
    rarities: list[str] = Field(default_factory=list)  # Unique rarities


class VaultListItem(BaseModel):
    """Summary for listing user's vaults."""

    id: str
    name: str
    visibility: VaultVisibility
    card_count: int
    total_value: Decimal | None = None
    view_count: int
    updated_at: datetime
    public_url: str | None = None
