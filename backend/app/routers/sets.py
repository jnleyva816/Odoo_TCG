"""Set management endpoints - list available sets and trigger imports."""

import base64
from typing import Annotated

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel

from ..services import OdooService, get_odoo_service

router = APIRouter(prefix="/sets", tags=["Sets"])

# TCGdex API base URL
TCGDEX_API = "https://api.tcgdex.net/v2/en"


class SetInfo(BaseModel):
    code: str
    name: str
    series: str | None = None
    release_date: str | None = None
    card_count: int = 0
    downloaded: bool = False
    downloaded_count: int = 0
    logo_url: str | None = None


class SetListResponse(BaseModel):
    sets: list[SetInfo]
    total: int


class ImportRequest(BaseModel):
    set_code: str


class ImportResponse(BaseModel):
    success: bool
    message: str
    set_code: str
    status: str = "queued"


# Track import status
_import_status: dict[str, dict] = {}


async def fetch_tcgdex_sets() -> list[dict]:
    """Fetch all sets from TCGdex API."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{TCGDEX_API}/sets")
        resp.raise_for_status()
        return resp.json()


async def fetch_tcgdex_set_detail(set_id: str) -> dict:
    """Fetch detailed set info from TCGdex API."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{TCGDEX_API}/sets/{set_id}")
        resp.raise_for_status()
        return resp.json()


@router.get("/available", response_model=SetListResponse)
async def get_available_sets(
    search: Annotated[str | None, Query(description="Search sets by name or code")] = None,
    show_downloaded: Annotated[bool, Query(description="Show only downloaded sets")] = False,
    series: Annotated[str | None, Query(description="Filter by series")] = None,
    odoo: OdooService = Depends(get_odoo_service),
) -> SetListResponse:
    """Get list of available sets from TCGdex with download status."""

    # Fetch all sets from TCGdex
    try:
        tcgdex_sets = await fetch_tcgdex_sets()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch sets from TCGdex: {e}")

    # Get categories from Odoo to check what's downloaded
    categories = await odoo.get_sets()
    downloaded_map: dict[str, int] = {}
    for c in categories:
        name = c.get("name", "").lower()
        downloaded_map[name] = c.get("product_count", 0)

    sets: list[SetInfo] = []
    for s in tcgdex_sets:
        set_id = s.get("id", "")
        set_name = s.get("name", "")
        set_series = s.get("series", {})
        series_name = set_series.get("name") if isinstance(set_series, dict) else None

        # Check if downloaded (category exists in Odoo)
        is_downloaded = False
        downloaded_count = 0
        set_name_lower = set_name.lower()
        for cat_name, count in downloaded_map.items():
            if set_name_lower in cat_name or set_id.lower() in cat_name:
                is_downloaded = True
                downloaded_count = count
                break

        # Apply filters
        if show_downloaded and not is_downloaded:
            continue

        if search:
            search_lower = search.lower()
            if (
                search_lower not in set_id.lower()
                and search_lower not in set_name.lower()
                and (not series_name or search_lower not in series_name.lower())
            ):
                continue

        if series:
            if not series_name or series.lower() not in series_name.lower():
                continue

        # Get card count from TCGdex data
        card_count = s.get("cardCount", {})
        total_cards = card_count.get("total", 0) if isinstance(card_count, dict) else 0

        sets.append(
            SetInfo(
                code=set_id,
                name=set_name,
                series=series_name,
                release_date=s.get("releaseDate"),
                card_count=total_cards,
                downloaded=is_downloaded,
                downloaded_count=downloaded_count,
                logo_url=s.get("logo"),
            )
        )

    # Sort by release date (newest first)
    sets.sort(key=lambda s: s.release_date or "", reverse=True)

    return SetListResponse(sets=sets, total=len(sets))


@router.get("/series")
async def get_series() -> list[str]:
    """Get list of all series names."""
    try:
        tcgdex_sets = await fetch_tcgdex_sets()
    except Exception:
        return []

    series_set = set()
    for s in tcgdex_sets:
        series = s.get("series", {})
        if isinstance(series, dict) and series.get("name"):
            series_set.add(series["name"])

    return sorted(series_set)


@router.get("/status/{set_code}")
async def get_import_status(set_code: str) -> dict:
    """Get the status of a set import."""
    if set_code in _import_status:
        return _import_status[set_code]
    return {"status": "unknown", "set_code": set_code}


@router.post("/import", response_model=ImportResponse)
async def import_set_endpoint(
    request: ImportRequest,
    background_tasks: BackgroundTasks,
    odoo: OdooService = Depends(get_odoo_service),
) -> ImportResponse:
    """Start importing a set from TCGdex in the background."""
    set_code = request.set_code.lower()

    # Check if already importing
    if set_code in _import_status and _import_status[set_code].get("status") == "importing":
        return ImportResponse(
            success=False,
            message="Set is already being imported",
            set_code=set_code,
            status="importing",
        )

    # Verify set exists
    try:
        set_data = await fetch_tcgdex_set_detail(set_code)
    except Exception:
        raise HTTPException(status_code=404, detail=f"Set not found: {set_code}")

    # Queue the import
    _import_status[set_code] = {
        "status": "queued",
        "message": "Import queued",
        "created": 0,
        "skipped": 0,
        "errors": 0,
    }

    background_tasks.add_task(run_tcgdex_import, set_code, set_data)

    return ImportResponse(
        success=True,
        message=f"Import started for {set_data.get('name', set_code)}",
        set_code=set_code,
        status="queued",
    )


async def run_tcgdex_import(set_code: str, set_data: dict):
    """Run the actual import from TCGdex in the background."""
    from ..services import get_odoo_service

    _import_status[set_code] = {
        "status": "importing",
        "message": "Fetching card data...",
        "created": 0,
        "skipped": 0,
        "errors": 0,
    }

    try:
        odoo = get_odoo_service()
        await odoo.connect()

        set_name = set_data.get("name", set_code)
        cards = set_data.get("cards", [])

        # Get or create category
        categories = await odoo.search_read(
            "product.category",
            [("name", "ilike", set_name)],
            ["id", "name"],
            limit=1,
        )

        if categories:
            category_id = categories[0]["id"]
        else:
            # Create category
            category_id = await odoo._execute(
                "product.category",
                "create",
                {"name": f"Pokemon / {set_name}"},
            )

        created = 0
        skipped = 0
        errors = 0

        async with httpx.AsyncClient(timeout=30) as client:
            for i, card in enumerate(cards):
                card_id = card.get("id", "")
                card_name = card.get("name", "Unknown")
                local_id = card.get("localId", "")

                _import_status[set_code][
                    "message"
                ] = f"Processing {i + 1}/{len(cards)}: {card_name}"

                sku = f"{set_code}-{local_id}".lower()
                display_name = f"{card_name} ({local_id})"

                # Check if exists
                existing = await odoo.search_read(
                    "product.product",
                    [("default_code", "=", sku)],
                    ["id"],
                    limit=1,
                )

                if existing:
                    skipped += 1
                    continue

                # Fetch card details for image
                image_b64 = None
                try:
                    card_detail = await client.get(f"{TCGDEX_API}/cards/{card_id}")
                    if card_detail.status_code == 200:
                        card_info = card_detail.json()
                        image_url = card_info.get("image")
                        if image_url:
                            # Get high quality image
                            img_resp = await client.get(f"{image_url}/high.png")
                            if img_resp.status_code == 200:
                                image_b64 = base64.b64encode(img_resp.content).decode()
                except Exception:
                    pass  # Skip image on error

                # Create product
                try:
                    await odoo._execute(
                        "product.product",
                        "create",
                        {
                            "name": display_name,
                            "default_code": sku,
                            "list_price": 0.0,  # No pricing from TCGdex
                            "categ_id": category_id,
                            "type": "product",
                            "image_1920": image_b64,
                        },
                    )
                    created += 1
                except Exception:
                    errors += 1

                _import_status[set_code]["created"] = created
                _import_status[set_code]["skipped"] = skipped
                _import_status[set_code]["errors"] = errors

        _import_status[set_code] = {
            "status": "complete",
            "message": f"Import complete! Created {created} cards.",
            "created": created,
            "skipped": skipped,
            "errors": errors,
        }

    except Exception as e:
        _import_status[set_code] = {
            "status": "error",
            "message": str(e),
            "created": 0,
            "skipped": 0,
            "errors": 1,
        }
