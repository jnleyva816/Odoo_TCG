"""Portfolio analytics models for the Wall Street Dashboard."""

from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class LiquidityTier(str, Enum):
    """Card liquidity classification."""

    HIGH = "high"  # Meta cards, Charizards, chase cards - sells in 24h
    MEDIUM = "medium"  # Popular cards, playable rares - sells in 1-7 days
    LOW = "low"  # Niche promos, bulk rares - sells in 7-30 days
    ILLIQUID = "illiquid"  # Bulk commons, damaged cards - hard to sell


class PriceMovement(BaseModel):
    """Price change for a single card."""

    product_id: int
    name: str
    sku: str
    set_name: str
    image_url: str | None = None
    current_price: Decimal
    previous_price: Decimal
    price_change: Decimal
    percent_change: float
    quantity_owned: int
    total_value_change: Decimal  # price_change * quantity


class PortfolioSummary(BaseModel):
    """Pre-calculated portfolio summary (materialized view)."""

    # Overall stats
    total_cards: int
    total_unique_cards: int
    total_value: Decimal
    total_cost_basis: Decimal = Decimal("0")  # What you paid
    unrealized_profit: Decimal = Decimal("0")  # total_value - cost_basis

    # Value changes
    value_24h_ago: Decimal = Decimal("0")
    value_7d_ago: Decimal = Decimal("0")
    value_30d_ago: Decimal = Decimal("0")
    change_24h: Decimal = Decimal("0")
    change_7d: Decimal = Decimal("0")
    change_30d: Decimal = Decimal("0")
    change_24h_percent: float = 0.0
    change_7d_percent: float = 0.0
    change_30d_percent: float = 0.0

    # Liquidity breakdown
    high_liquidity_value: Decimal = Decimal("0")
    medium_liquidity_value: Decimal = Decimal("0")
    low_liquidity_value: Decimal = Decimal("0")
    illiquid_value: Decimal = Decimal("0")

    # Top categories
    top_sets: list[dict] = Field(default_factory=list)  # [{name, value, count}]
    top_cards_by_value: list[dict] = Field(default_factory=list)

    # Calculated at
    calculated_at: datetime = Field(default_factory=datetime.utcnow)


class TopMover(BaseModel):
    """A card with significant price movement."""

    product_id: int
    name: str
    sku: str
    set_name: str
    image_url: str | None = None
    current_price: Decimal
    price_change_24h: Decimal
    percent_change_24h: float
    quantity_owned: int
    direction: str = "up"  # "up" or "down"


class CostBasisEntry(BaseModel):
    """Cost basis tracking for a purchase."""

    id: int | None = None
    product_id: int
    quantity: int
    cost_per_unit: Decimal
    total_cost: Decimal
    purchase_date: datetime
    notes: str | None = None


class CostBasisInput(BaseModel):
    """Input for adding cost basis."""

    product_id: int
    quantity: int
    total_cost: Decimal  # Total paid for the lot
    purchase_date: datetime | None = None
    notes: str | None = None


class PortfolioStats(BaseModel):
    """Complete portfolio analytics response."""

    summary: PortfolioSummary
    top_gainers: list[TopMover] = Field(default_factory=list)
    top_losers: list[TopMover] = Field(default_factory=list)
    recent_price_changes: list[PriceMovement] = Field(default_factory=list)

