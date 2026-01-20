"""Card search and detail endpoints."""

import json
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth.dependencies import get_current_user
from ..models import Card, CardDetail, CardSearchResult, SetInfo
from ..services import OdooService, get_odoo_service

if TYPE_CHECKING:
    from ..auth.models import User

router = APIRouter(prefix="/cards", tags=["Cards"])

# Load static logo mapping from JSON file
_logo_mapping: dict[str, str] = {}
_logo_file = Path(__file__).parent.parent / "data" / "set_logos.json"
if _logo_file.exists():
    with open(_logo_file) as f:
        _logo_mapping = json.load(f)


def get_logo_for_set(set_name: str) -> str | None:
    """Get logo URL for a set by name from static mapping."""
    name_lower = set_name.lower()

    # Remove common prefixes like "SV03: " for matching
    clean_name = name_lower
    if ": " in clean_name:
        clean_name = clean_name.split(": ", 1)[1]

    # Try exact match
    if name_lower in _logo_mapping:
        return _logo_mapping[name_lower]
    if clean_name in _logo_mapping:
        return _logo_mapping[clean_name]

    # Fuzzy match
    for cached_name, logo in _logo_mapping.items():
        if clean_name in cached_name or cached_name in clean_name:
            return logo

    return None


def _odoo_str(value: Any) -> str | None:
    """Convert Odoo value to string, handling False → None."""
    if value is False or value is None:
        return None
    return str(value)


def _record_to_card_detail(record: dict[str, Any]) -> CardDetail:
    """Convert Odoo record to CardDetail model."""
    return CardDetail(
        id=record["id"],
        sku=record.get("default_code") or "",
        name=record.get("name") or "",
        set_name=record["categ_id"][1] if record.get("categ_id") else None,
        quantity=int(record.get("qty_available") or 0),
        price=Decimal(str(record.get("list_price") or 0)),
        has_image=bool(record.get("image_256")),
        barcode=_odoo_str(record.get("barcode")),
        image_url=f"/api/images/{record['id']}",
        variant=None,
        card_number=None,
        rarity=None,
    )


@router.get("/search", response_model=CardSearchResult)
async def search_cards(
    q: Annotated[str, Query(min_length=1, description="Search query")],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    odoo: OdooService = Depends(get_odoo_service),
) -> CardSearchResult:
    """Search for cards by SKU or name."""
    records = await odoo.search_products(q, limit=limit)

    cards = [
        Card(
            id=r["id"],
            sku=r.get("default_code") or "",
            name=r.get("name") or "",
            set_name=r["categ_id"][1] if r.get("categ_id") else None,
            quantity=int(r.get("qty_available") or 0),
            price=Decimal(str(r.get("list_price") or 0)),
            has_image=bool(r.get("image_256")),
        )
        for r in records
    ]

    return CardSearchResult(cards=cards, total=len(cards), query=q)


@router.get("/sku/{sku}", response_model=CardDetail)
async def get_card_by_sku(
    sku: str,
    odoo: OdooService = Depends(get_odoo_service),
) -> CardDetail:
    """Get detailed card information by SKU."""
    record = await odoo.get_product_by_sku(sku)
    if not record:
        raise HTTPException(status_code=404, detail=f"Card with SKU '{sku}' not found")

    return _record_to_card_detail(record)


@router.get("/{card_id}", response_model=CardDetail)
async def get_card_detail(
    card_id: int,
    odoo: OdooService = Depends(get_odoo_service),
    current_user: "User" = Depends(get_current_user),
) -> CardDetail:
    """Get detailed card information by ID (warehouse-aware)."""
    # Use warehouse-specific quantity if user has an active warehouse
    warehouse_id = current_user.warehouse_id if current_user else None

    if warehouse_id:
        # Get product with warehouse-specific quantity
        qty = await odoo.get_product_quantity_in_warehouse(card_id, warehouse_id)
        records = await odoo.read(
            "product.product",
            [card_id],
            [
                "id",
                "default_code",
                "name",
                "list_price",
                "categ_id",
                "barcode",
                "image_256",
            ],
        )
        if records:
            records[0]["qty_available"] = qty
    else:
        records = await odoo.read(
            "product.product",
            [card_id],
            [
                "id",
                "default_code",
                "name",
                "qty_available",
                "list_price",
                "categ_id",
                "barcode",
                "image_256",
            ],
        )

    if not records:
        raise HTTPException(status_code=404, detail=f"Card with ID {card_id} not found")

    return _record_to_card_detail(records[0])


@router.get("/sets/", response_model=list[SetInfo])
async def get_sets(
    odoo: OdooService = Depends(get_odoo_service),
) -> list[SetInfo]:
    """Get all card sets (categories) with logos."""
    records = await odoo.get_sets()

    return [
        SetInfo(
            id=r["id"],
            name=r.get("name") or "",
            card_count=r.get("product_count") or 0,
            logo_url=get_logo_for_set(r.get("name") or ""),
        )
        for r in records
    ]
