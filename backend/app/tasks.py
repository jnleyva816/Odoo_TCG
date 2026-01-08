"""Celery tasks for background processing.

These tasks run in the Celery worker, separate from the FastAPI server.
"""

import asyncio

from .config import get_settings
from .services.odoo import OdooService
from .services.search import SearchService
from .worker import celery_app


def run_async(coro):
    """Run async function in sync context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, max_retries=3)
def sync_all_cards_to_search(self, warehouse_id: int | None = None):
    """
    Sync all cards from Odoo to Meilisearch.

    This task fetches all products from Odoo and indexes them
    in Meilisearch for fast searching.
    """
    async def _sync():
        settings = get_settings()
        odoo = OdooService(settings)
        search = SearchService(settings)

        await odoo.connect()
        await search.initialize()

        # Fetch all cards from Odoo
        page = 1
        page_size = 500
        total_indexed = 0

        while True:
            records, total = await odoo.get_inventory(
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
            await search.index_cards(cards)
            total_indexed += len(cards)

            print(f"📦 Indexed {total_indexed}/{total} cards")

            if page * page_size >= total:
                break
            page += 1

        await search.close()
        return {"indexed": total_indexed, "warehouse_id": warehouse_id}

    try:
        return run_async(_sync())
    except Exception as e:
        print(f"❌ Sync failed: {e}")
        raise self.retry(exc=e, countdown=60)


@celery_app.task(bind=True, max_retries=3)
def sync_card_to_search(self, card_id: int, warehouse_id: int | None = None):
    """Sync a single card to Meilisearch (for real-time updates)."""
    async def _sync():
        settings = get_settings()
        odoo = OdooService(settings)
        search = SearchService(settings)

        await odoo.connect()
        await search.initialize()

        # Fetch card from Odoo
        records = await odoo.read(
            "product.product",
            [card_id],
            ["id", "default_code", "name", "categ_id", "list_price", "qty_available"],
        )

        if not records:
            return {"error": "Card not found"}

        r = records[0]

        # Get warehouse-specific quantity if needed
        quantity = int(r.get("qty_available") or 0)
        if warehouse_id:
            quantity = await odoo.get_product_quantity_in_warehouse(card_id, warehouse_id)

        card = {
            "id": r["id"],
            "sku": r.get("default_code") or "",
            "name": r.get("name") or "",
            "set_id": r["categ_id"][0] if r.get("categ_id") else None,
            "set_name": r["categ_id"][1] if r.get("categ_id") else None,
            "price": float(r.get("list_price") or 0),
            "quantity": quantity,
            "has_stock": quantity > 0,
            "warehouse_id": warehouse_id,
        }

        await search.index_cards([card])
        await search.close()

        return {"indexed": 1, "card_id": card_id}

    try:
        return run_async(_sync())
    except Exception as e:
        print(f"❌ Card sync failed: {e}")
        raise self.retry(exc=e, countdown=30)


@celery_app.task(bind=True, max_retries=3)
def import_set_task(self, set_code: str, skip_images: bool = False):
    """
    Import a card set from external source (e.g., Pokemon TCG API).

    This is a placeholder - implement based on your data source.
    """
    # TODO: Implement set import logic
    return {"status": "not_implemented", "set_code": set_code}


@celery_app.task(bind=True, max_retries=3)
def sync_prices_task(self):
    """
    Sync prices from TCGPlayer or other pricing source.

    This is a placeholder - implement based on your pricing source.
    """
    # TODO: Implement price sync logic
    return {"status": "not_implemented"}

