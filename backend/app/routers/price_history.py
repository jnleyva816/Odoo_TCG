"""Price history API endpoints."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..auth.dependencies import get_current_user
from ..services import price_history

router = APIRouter(prefix="/prices", tags=["Price History"])


class PriceRecord(BaseModel):
    """A single price record."""

    id: int
    product_sku: str
    price: Decimal
    low_price: Decimal | None
    mid_price: Decimal | None
    high_price: Decimal | None
    market_price: Decimal | None
    recorded_at: datetime
    source: str


class PriceHistoryResponse(BaseModel):
    """Price history for a product."""

    sku: str
    history: list[PriceRecord]
    total: int


class PriceChangeRecord(BaseModel):
    """A price change record."""

    product_sku: str
    current_price: Decimal
    prev_price: Decimal
    recorded_at: datetime
    change_percent: Decimal


@router.get("/history/{sku}", response_model=PriceHistoryResponse)
async def get_price_history(
    sku: str,
    limit: Annotated[int, Query(ge=1, le=365)] = 30,
    current_user=Depends(get_current_user),
) -> PriceHistoryResponse:
    """Get price history for a product by SKU."""
    history = await price_history.get_price_history(sku, limit=limit)

    return PriceHistoryResponse(
        sku=sku,
        history=[PriceRecord(**record) for record in history],
        total=len(history),
    )


@router.get("/changes", response_model=list[PriceChangeRecord])
async def get_price_changes(
    days: Annotated[int, Query(ge=1, le=30)] = 1,
    min_change: Annotated[float, Query(ge=0)] = 5.0,
    current_user=Depends(get_current_user),
) -> list[PriceChangeRecord]:
    """Get products with significant price changes."""
    changes = await price_history.get_price_changes(
        days=days,
        min_change_percent=min_change,
    )

    return [PriceChangeRecord(**record) for record in changes]


@router.post("/init")
async def init_table(
    current_user=Depends(get_current_user),
) -> dict:
    """Initialize the price history table (admin only)."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    await price_history.init_price_history_table()
    return {"status": "ok", "message": "Price history table initialized"}
