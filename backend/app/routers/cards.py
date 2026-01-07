"""Card search and detail endpoints."""

from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from ..models import Card, CardDetail, CardSearchResult, SetInfo
from ..services import OdooService, get_odoo_service

router = APIRouter(prefix="/cards", tags=["Cards"])


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
) -> CardDetail:
    """Get detailed card information by ID."""
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
    """Get all card sets (categories)."""
    records = await odoo.get_sets()

    return [
        SetInfo(
            id=r["id"],
            name=r.get("name") or "",
            card_count=r.get("product_count") or 0,
        )
        for r in records
    ]
