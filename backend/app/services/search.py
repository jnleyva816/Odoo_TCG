"""Meilisearch service for fast full-text search.

This provides instant, typo-tolerant search for cards,
significantly faster than querying Odoo directly.
"""

from typing import Any

import httpx

from ..config import Settings, get_settings


class SearchService:
    """Meilisearch-based search service."""

    INDEX_NAME = "cards"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = settings.meili_url
        self.api_key = settings.meili_master_key
        self._client: httpx.AsyncClient | None = None
        self._initialized = False

    def _get_headers(self) -> dict[str, str]:
        """Get headers for Meilisearch API."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self._get_headers(),
                timeout=30.0,
            )
        return self._client

    async def health_check(self) -> bool:
        """Check if Meilisearch is healthy."""
        try:
            client = await self._get_client()
            response = await client.get("/health")
            return response.status_code == 200
        except Exception:
            return False

    async def initialize(self) -> bool:
        """Initialize the search index with proper settings."""
        if self._initialized:
            return True

        try:
            client = await self._get_client()

            # Create or update index
            await client.post(
                "/indexes",
                json={"uid": self.INDEX_NAME, "primaryKey": "id"},
            )

            # Configure searchable and filterable attributes
            await client.patch(
                f"/indexes/{self.INDEX_NAME}/settings",
                json={
                    "searchableAttributes": [
                        "name",
                        "sku",
                        "set_name",
                        "card_number",
                        "rarity",
                    ],
                    "filterableAttributes": [
                        "set_id",
                        "set_name",
                        "rarity",
                        "has_stock",
                        "warehouse_id",
                    ],
                    "sortableAttributes": [
                        "name",
                        "sku",
                        "price",
                        "quantity",
                    ],
                    "rankingRules": [
                        "words",
                        "typo",
                        "proximity",
                        "attribute",
                        "sort",
                        "exactness",
                    ],
                    "typoTolerance": {
                        "enabled": True,
                        "minWordSizeForTypos": {
                            "oneTypo": 4,
                            "twoTypos": 8,
                        },
                    },
                },
            )

            self._initialized = True
            print("✅ Meilisearch index initialized")
            return True

        except Exception as e:
            print(f"⚠️ Failed to initialize Meilisearch: {e}")
            return False

    async def index_cards(self, cards: list[dict[str, Any]]) -> bool:
        """Index a batch of cards.

        Args:
            cards: List of card documents to index. Each should have:
                - id: Unique identifier (Odoo product ID)
                - sku: Product SKU/default_code
                - name: Card name
                - set_id: Category/set ID
                - set_name: Category/set name
                - price: List price
                - quantity: Stock quantity
                - warehouse_id: Warehouse ID (for filtering)
                - has_stock: Boolean for quick filtering
        """
        if not cards:
            return True

        try:
            client = await self._get_client()
            response = await client.post(
                f"/indexes/{self.INDEX_NAME}/documents",
                json=cards,
            )
            return response.status_code in (200, 202)
        except Exception as e:
            print(f"⚠️ Failed to index cards: {e}")
            return False

    async def delete_cards(self, card_ids: list[int]) -> bool:
        """Delete cards from index."""
        if not card_ids:
            return True

        try:
            client = await self._get_client()
            response = await client.post(
                f"/indexes/{self.INDEX_NAME}/documents/delete-batch",
                json=card_ids,
            )
            return response.status_code in (200, 202)
        except Exception as e:
            print(f"⚠️ Failed to delete cards: {e}")
            return False

    async def search(
        self,
        query: str,
        warehouse_id: int | None = None,
        set_id: int | None = None,
        stock_filter: str = "all",
        sort_by: str = "sku",
        sort_order: str = "asc",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """
        Search cards with instant results.

        Returns:
            Tuple of (results, total_hits)
        """
        try:
            client = await self._get_client()

            # Build filter
            # Note: We don't filter by warehouse_id in Meilisearch because
            # card catalog is shared across warehouses - only stock differs.
            # Stock filtering happens via Odoo's real-time inventory.
            filters = []
            if set_id:
                filters.append(f"set_id = {set_id}")
            if stock_filter == "in_stock":
                filters.append("has_stock = true")
            elif stock_filter == "out_of_stock":
                filters.append("has_stock = false")

            # Build sort
            sort_field_map = {
                "sku": "sku",
                "name": "name",
                "quantity": "quantity",
                "price": "price",
            }
            sort_field = sort_field_map.get(sort_by, "sku")
            sort = [f"{sort_field}:{sort_order}"]

            # Calculate offset
            offset = (page - 1) * page_size

            # Search request
            search_params: dict[str, Any] = {
                "q": query,
                "limit": page_size,
                "offset": offset,
                "sort": sort,
            }

            if filters:
                search_params["filter"] = " AND ".join(filters)

            response = await client.post(
                f"/indexes/{self.INDEX_NAME}/search",
                json=search_params,
            )

            if response.status_code != 200:
                return [], 0

            data = response.json()
            return data.get("hits", []), data.get("estimatedTotalHits", 0)

        except Exception as e:
            print(f"⚠️ Search failed: {e}")
            return [], 0

    async def get_stats(self) -> dict[str, Any]:
        """Get index statistics."""
        try:
            client = await self._get_client()
            response = await client.get(f"/indexes/{self.INDEX_NAME}/stats")
            if response.status_code == 200:
                return response.json()
        except Exception:
            pass
        return {}

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Singleton instance
_search_service: SearchService | None = None


def get_search_service() -> SearchService:
    """Get the search service singleton."""
    global _search_service
    if _search_service is None:
        _search_service = SearchService(get_settings())
    return _search_service
