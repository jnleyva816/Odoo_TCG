"""Search API endpoints using Meilisearch.

This provides instant, typo-tolerant search for cards.
Falls back to Odoo search if Meilisearch is unavailable.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from ..auth.dependencies import get_current_user
from ..auth.models import User
from ..services import SearchService, get_search_service, OdooService, get_odoo_service
from ..models.inventory import SortField, SortOrder
from pydantic import BaseModel


router = APIRouter(prefix="/search", tags=["Search"])


class SearchResult(BaseModel):
    """Search result item."""
    id: int
    sku: str
    name: str
    set_name: str | None = None
    price: float
    quantity: int
    has_stock: bool
    image_url: str | None = None


class SearchResponse(BaseModel):
    """Search response."""
    query: str
    results: list[SearchResult]
    total: int
    page: int
    page_size: int
    source: str  # "meilisearch" or "odoo"


@router.get("", response_model=SearchResponse)
@router.get("/", response_model=SearchResponse)
async def search_cards(
    q: Annotated[str, Query(description="Search query", min_length=1)] = "",
    set_id: Annotated[int | None, Query(description="Filter by set ID")] = None,
    stock: Annotated[str, Query(description="Stock filter: all, in_stock, out_of_stock")] = "all",
    sort_by: Annotated[str, Query(description="Sort by: sku, name, quantity, price")] = "sku",
    order: Annotated[str, Query(description="Sort order: asc, desc")] = "asc",
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    current_user: User = Depends(get_current_user),
    search_service: SearchService = Depends(get_search_service),
    odoo_service: OdooService = Depends(get_odoo_service),
) -> SearchResponse:
    """
    Search cards with instant results.
    
    Uses Meilisearch for fast, typo-tolerant search.
    Falls back to Odoo if Meilisearch is unavailable.
    """
    warehouse_id = current_user.warehouse_id
    
    # Try Meilisearch first (only if it has data)
    if await search_service.health_check():
        # Check if Meilisearch has any indexed documents
        stats = await search_service.get_stats()
        if stats.get("numberOfDocuments", 0) > 0:
            results, total = await search_service.search(
                query=q,
                warehouse_id=warehouse_id,
                set_id=set_id,
                stock_filter=stock,
                sort_by=sort_by,
                sort_order=order,
                page=page,
                page_size=page_size,
            )
            
            return SearchResponse(
                query=q,
                results=[
                    SearchResult(
                        id=r["id"],
                        sku=r.get("sku", ""),
                        name=r.get("name", ""),
                        set_name=r.get("set_name"),
                        price=r.get("price", 0),
                        quantity=r.get("quantity", 0),
                        has_stock=r.get("has_stock", False),
                        image_url=f"/api/images/{r['id']}",
                    )
                    for r in results
                ],
                total=total,
                page=page,
                page_size=page_size,
                source="meilisearch",
            )
        # Meilisearch has no data, fall through to Odoo
    
    # Fallback to Odoo search
    records, total = await odoo_service.get_inventory(
        search=q if q else None,
        set_id=set_id,
        stock_filter=stock,
        sort_by=sort_by,
        sort_order=order,
        page=page,
        page_size=page_size,
        warehouse_id=warehouse_id,
    )
    
    return SearchResponse(
        query=q,
        results=[
            SearchResult(
                id=r["id"],
                sku=r.get("default_code", ""),
                name=r.get("name", ""),
                set_name=r["categ_id"][1] if r.get("categ_id") else None,
                price=float(r.get("list_price", 0)),
                quantity=int(r.get("qty_available", 0)),
                has_stock=int(r.get("qty_available", 0)) > 0,
                image_url=f"/api/images/{r['id']}",
            )
            for r in records
        ],
        total=total,
        page=page,
        page_size=page_size,
        source="odoo",
    )


@router.get("/stats")
async def get_search_stats(
    current_user: User = Depends(get_current_user),
    search_service: SearchService = Depends(get_search_service),
):
    """Get search index statistics."""
    healthy = await search_service.health_check()
    stats = await search_service.get_stats() if healthy else {}
    
    return {
        "healthy": healthy,
        "index": search_service.INDEX_NAME,
        "stats": stats,
    }


@router.post("/sync")
async def trigger_sync(
    current_user: User = Depends(get_current_user),
    search_service: SearchService = Depends(get_search_service),
    odoo_service: OdooService = Depends(get_odoo_service),
):
    """
    Sync all cards from Odoo to Meilisearch.
    
    This runs directly (not via Celery) and indexes all cards.
    """
    # Initialize Meilisearch index
    await search_service.initialize()
    
    # Fetch all cards from Odoo and index them
    page = 1
    page_size = 500
    total_indexed = 0
    warehouse_id = current_user.warehouse_id
    
    while True:
        records, total = await odoo_service.get_inventory(
            page=page,
            page_size=page_size,
            warehouse_id=warehouse_id,
        )
        
        if not records:
            break
        
        # Transform for Meilisearch
        cards = []
        for r in records:
            cards.append({
                "id": r["id"],
                "sku": r.get("default_code") or "",
                "name": r.get("name") or "",
                "set_id": r["categ_id"][0] if r.get("categ_id") else None,
                "set_name": r["categ_id"][1] if r.get("categ_id") else None,
                "price": float(r.get("list_price") or 0),
                "quantity": int(r.get("qty_available") or 0),
                "has_stock": int(r.get("qty_available") or 0) > 0,
                "warehouse_id": warehouse_id,
            })
        
        # Index batch
        await search_service.index_cards(cards)
        total_indexed += len(cards)
        
        if page * page_size >= total:
            break
        page += 1
    
    return {
        "status": "complete",
        "indexed": total_indexed,
        "warehouse_id": warehouse_id,
        "message": f"Successfully indexed {total_indexed} cards to Meilisearch",
    }

