"""Inventory management endpoints."""

import math
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


@router.get("/", response_model=InventoryResponse)
async def get_inventory(
    search: Annotated[str | None, Query(description="Search by name or SKU")] = None,
    set_id: Annotated[int | None, Query(description="Filter by set/category ID")] = None,
    stock: Annotated[StockFilter, Query(description="Filter by stock status")] = StockFilter.ALL,
    sort_by: Annotated[SortField, Query(description="Sort field")] = SortField.SKU,
    order: Annotated[SortOrder, Query(description="Sort order")] = SortOrder.ASC,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
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
