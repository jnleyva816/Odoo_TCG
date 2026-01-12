"""Inventory management endpoints."""

import math
import re
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth.dependencies import get_current_user
from ..auth.models import User
from ..models import (
    InventoryItem,
    InventoryResponse,
    StockAdjustment,
    StockFilter,
)
from ..models.inventory import SortField, SortOrder
from ..services import OdooService, get_odoo_service

router = APIRouter(prefix="/inventory", tags=["Inventory"])


def extract_base_name(name: str) -> tuple[str, str | None]:
    """Extract base card name and variant from full name.

    Returns (base_name, variant)
    Examples:
        "Pikachu (001) (Reverse Holo)" -> ("Pikachu (001)", "Reverse Holo")
        "Charizard (006) - Holo" -> ("Charizard (006)", "Holo")
        "Bulbasaur (001)" -> ("Bulbasaur (001)", None)
    """
    variant_patterns = [
        r"\s*\((Reverse Holo(?:foil)?)\)\s*$",
        r"\s*\((Holo(?:foil)?)\)\s*$",
        r"\s*\((Cosmos Holo)\)\s*$",
        r"\s*-\s*(Reverse Holo(?:foil)?)\s*$",
        r"\s*-\s*(Holo(?:foil)?)\s*$",
    ]

    variant = None
    base_name = name

    for pattern in variant_patterns:
        match = re.search(pattern, name, re.IGNORECASE)
        if match:
            variant = match.group(1)
            base_name = name[: match.start()].strip()
            break

    return base_name, variant


@router.get("/", response_model=InventoryResponse)
async def get_inventory(
    search: Annotated[str | None, Query(description="Search by name or SKU")] = None,
    set_id: Annotated[int | None, Query(description="Filter by set/category ID")] = None,
    stock: Annotated[StockFilter, Query(description="Filter by stock status")] = StockFilter.ALL,
    sort_by: Annotated[SortField, Query(description="Sort field")] = SortField.SKU,
    order: Annotated[SortOrder, Query(description="Sort order")] = SortOrder.ASC,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=500, description="Items per page")] = 20,
    current_user: User = Depends(get_current_user),
    odoo: OdooService = Depends(get_odoo_service),
) -> InventoryResponse:
    """Get paginated inventory with filtering, searching, and sorting.

    Inventory is filtered by the user's active warehouse.
    """
    records, total = await odoo.get_inventory(
        search=search,
        set_id=set_id,
        stock_filter=stock.value,
        sort_by=sort_by.value,
        sort_order=order.value,
        page=page,
        page_size=page_size,
        warehouse_id=current_user.warehouse_id,
    )

    items = [
        InventoryItem(
            id=r["id"],
            sku=r.get("default_code") or "",
            name=r.get("name") or "",
            set_name=r["categ_id"][1] if r.get("categ_id") else None,
            quantity=int(r.get("qty_available") or 0),
            price=Decimal(str(r.get("list_price") or 0)),
            has_image=True,  # Assume all have images for inventory
            image_url=f"/api/images/{r['id']}",
        )
        for r in records
    ]

    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return InventoryResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("/adjust", response_model=dict)
async def adjust_stock(
    adjustment: StockAdjustment,
    current_user: User = Depends(get_current_user),
    odoo: OdooService = Depends(get_odoo_service),
) -> dict:
    """Adjust stock quantity for a product in the user's active warehouse."""
    success = await odoo.adjust_stock(
        product_id=adjustment.product_id,
        quantity_change=adjustment.quantity_change,
        warehouse_id=current_user.warehouse_id,
    )

    if not success:
        raise HTTPException(
            status_code=400,
            detail="Failed to adjust stock. Product may not exist.",
        )

    # Get updated quantity for this warehouse
    if current_user.warehouse_id:
        new_quantity = await odoo.get_product_quantity_in_warehouse(
            adjustment.product_id, current_user.warehouse_id
        )
    else:
        records = await odoo.read(
            "product.product",
            [adjustment.product_id],
            ["qty_available"],
        )
        new_quantity = int(records[0].get("qty_available", 0)) if records else 0

    return {
        "success": True,
        "product_id": adjustment.product_id,
        "new_quantity": new_quantity,
        "change": adjustment.quantity_change,
    }


@router.get("/{product_id}/variants", response_model=list[InventoryItem])
async def get_card_variants(
    product_id: int,
    current_user: User = Depends(get_current_user),
    odoo: OdooService = Depends(get_odoo_service),
) -> list[InventoryItem]:
    """Get all variants of a card (e.g., Normal, Holo, Reverse Holo).

    Finds cards with the same base name (without variant suffix) in the same set.
    """
    # Get the current card
    records = await odoo.read(
        "product.product",
        [product_id],
        ["name", "categ_id", "default_code", "list_price", "qty_available"],
    )

    if not records:
        raise HTTPException(status_code=404, detail="Card not found")

    card = records[0]
    base_name, _ = extract_base_name(card.get("name") or "")
    set_id = card.get("categ_id", [None])[0] if card.get("categ_id") else None

    if not set_id:
        # No set, just return this card
        return [
            InventoryItem(
                id=card["id"],
                sku=card.get("default_code") or "",
                name=card.get("name") or "",
                set_name=None,
                quantity=int(card.get("qty_available") or 0),
                price=Decimal(str(card.get("list_price") or 0)),
                has_image=True,
                image_url=f"/api/images/{card['id']}",
            )
        ]

    # Search for cards with similar names in the same set
    # Use ilike for case-insensitive search with the base name
    search_domain = [
        ("categ_id", "=", set_id),
        ("name", "ilike", base_name),
    ]

    variant_records = await odoo.search_read(
        "product.product",
        search_domain,
        ["id", "name", "default_code", "list_price", "qty_available", "categ_id"],
        order="default_code",
    )

    # Filter to only include true variants (same base name)
    variants = []
    for r in variant_records:
        r_base, r_variant = extract_base_name(r.get("name") or "")
        if r_base.lower() == base_name.lower():
            variants.append(
                InventoryItem(
                    id=r["id"],
                    sku=r.get("default_code") or "",
                    name=r.get("name") or "",
                    set_name=r["categ_id"][1] if r.get("categ_id") else None,
                    quantity=int(r.get("qty_available") or 0),
                    price=Decimal(str(r.get("list_price") or 0)),
                    has_image=True,
                    image_url=f"/api/images/{r['id']}",
                )
            )

    # Sort: Normal first, then alphabetically by variant
    def variant_sort_key(item: InventoryItem) -> tuple[int, str]:
        _, variant = extract_base_name(item.name)
        if variant is None:
            return (0, "")  # Normal comes first
        return (1, variant.lower())

    variants.sort(key=variant_sort_key)

    return variants
