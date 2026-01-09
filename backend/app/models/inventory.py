"""Inventory-related Pydantic models."""

from enum import Enum

from pydantic import BaseModel, Field

from .card import Card


class StockFilter(str, Enum):
    """Stock filter options."""

    ALL = "all"
    IN_STOCK = "in_stock"
    OUT_OF_STOCK = "out_of_stock"


class SortField(str, Enum):
    """Sortable fields."""

    SKU = "sku"
    NAME = "name"
    QUANTITY = "quantity"
    PRICE = "price"
    RECENT = "recent"


class SortOrder(str, Enum):
    """Sort order."""

    ASC = "asc"
    DESC = "desc"


class InventoryItem(Card):
    """Inventory item with additional display info."""

    image_url: str = Field(..., description="URL to fetch card image")


class InventoryResponse(BaseModel):
    """Paginated inventory response."""

    items: list[InventoryItem] = Field(default_factory=list)
    total: int = Field(0, description="Total items matching filter")
    page: int = Field(1, description="Current page number")
    page_size: int = Field(20, description="Items per page")
    total_pages: int = Field(0, description="Total number of pages")


class StockAdjustment(BaseModel):
    """Request to adjust stock quantity."""

    product_id: int = Field(..., description="Odoo product ID")
    quantity_change: int = Field(..., description="Amount to add (positive) or remove (negative)")
    reason: str | None = Field(None, description="Optional reason for adjustment")
