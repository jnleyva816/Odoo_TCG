"""Async Odoo XML-RPC service with thread-safe connections."""

import asyncio
import base64
import threading
import xmlrpc.client
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Any

from ..config import Settings, get_settings


class OdooConnection:
    """Thread-local Odoo connection wrapper."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._local = threading.local()

    def _get_models(self) -> xmlrpc.client.ServerProxy:
        """Get or create a thread-local ServerProxy for models."""
        if not hasattr(self._local, "models") or self._local.models is None:
            self._local.models = xmlrpc.client.ServerProxy(
                f"{self.settings.odoo_url}/xmlrpc/2/object",
                allow_none=True,
            )
        return self._local.models

    def _get_uid(self) -> int:
        """Get or create a thread-local UID."""
        if not hasattr(self._local, "uid") or self._local.uid is None:
            common = xmlrpc.client.ServerProxy(
                f"{self.settings.odoo_url}/xmlrpc/2/common",
                allow_none=True,
            )
            self._local.uid = common.authenticate(
                self.settings.odoo_db,
                self.settings.odoo_user,
                self.settings.odoo_password,
                {},
            )
        return self._local.uid

    def execute(self, model: str, method: str, *args: Any, **kwargs: Any) -> Any:
        """Execute Odoo method with thread-local connection."""
        models = self._get_models()
        uid = self._get_uid()

        return models.execute_kw(
            self.settings.odoo_db,
            uid,
            self.settings.odoo_password,
            model,
            method,
            list(args),
            kwargs,
        )


class OdooService:
    """Async wrapper around Odoo XML-RPC API."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._connection = OdooConnection(settings)
        self._executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="odoo")
        self._connected = False

    async def connect(self) -> bool:
        """Test connection to Odoo."""
        loop = asyncio.get_event_loop()
        try:
            # Test authentication
            uid = await loop.run_in_executor(
                self._executor,
                self._connection._get_uid,
            )
            self._connected = uid is not None and uid > 0
            return self._connected
        except Exception as e:
            print(f"⚠️  Odoo connection failed: {e}")
            self._connected = False
            return False

    async def _execute(
        self,
        model: str,
        method: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute an Odoo model method asynchronously."""
        loop = asyncio.get_event_loop()
        # Capture args/kwargs in closure to avoid issues
        call_args = args
        call_kwargs = kwargs
        return await loop.run_in_executor(
            self._executor,
            lambda: self._connection.execute(model, method, *call_args, **call_kwargs),
        )

    async def search_read(
        self,
        model: str,
        domain: list[Any],
        fields: list[str],
        offset: int = 0,
        limit: int | None = None,
        order: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search and read records from Odoo."""
        kwargs: dict[str, Any] = {"fields": fields}
        if offset:
            kwargs["offset"] = offset
        if limit:
            kwargs["limit"] = limit
        if order:
            kwargs["order"] = order

        return await self._execute(model, "search_read", domain, **kwargs)

    async def search_count(self, model: str, domain: list[Any]) -> int:
        """Count matching records."""
        return await self._execute(model, "search_count", domain)

    async def read(
        self,
        model: str,
        ids: list[int],
        fields: list[str],
    ) -> list[dict[str, Any]]:
        """Read specific records by ID."""
        # Odoo read() takes ids and fields as positional args
        return await self._execute(model, "read", ids, fields)

    async def write(
        self,
        model: str,
        ids: list[int],
        values: dict[str, Any],
    ) -> bool:
        """Update records."""
        # Odoo write() takes ids and values as positional args
        return await self._execute(model, "write", ids, values)

    async def get_product_image(
        self,
        product_id: int,
        size: str = "image_256",
    ) -> bytes | None:
        """Fetch product image as bytes."""
        try:
            records = await self.read("product.product", [product_id], [size])
            if records and records[0].get(size):
                return base64.b64decode(records[0][size])
        except Exception:
            pass
        return None

    async def search_products(
        self,
        query: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Search products by SKU or name."""
        domain = [
            "|",
            ("default_code", "ilike", query),
            ("name", "ilike", query),
        ]
        return await self.search_read(
            "product.product",
            domain,
            [
                "id",
                "default_code",
                "name",
                "qty_available",
                "list_price",
                "categ_id",
                "image_256",
            ],
            limit=limit,
            order="default_code",
        )

    async def get_product_by_sku(self, sku: str) -> dict[str, Any] | None:
        """Get a single product by SKU."""
        records = await self.search_read(
            "product.product",
            [("default_code", "=", sku)],
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
            limit=1,
        )
        return records[0] if records else None

    async def get_inventory(
        self,
        search: str | None = None,
        set_id: int | None = None,
        stock_filter: str = "all",
        sort_by: str = "sku",
        sort_order: str = "asc",
        page: int = 1,
        page_size: int = 20,
        warehouse_id: int | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """Get paginated inventory with filtering, searching, and sorting.

        If warehouse_id is provided, quantities are computed for that specific warehouse.
        """
        # Build domain
        domain: list[Any] = []

        # Search filter
        if search:
            domain.append("|")
            domain.append(("default_code", "ilike", search))
            domain.append(("name", "ilike", search))

        if set_id:
            domain.append(("categ_id", "=", set_id))

        # Map sort fields to Odoo field names
        sort_map = {
            "sku": "default_code",
            "name": "name",
            "quantity": "qty_available",
            "price": "list_price",
        }
        order_field = sort_map.get(sort_by, "default_code")
        order = f"{order_field} {sort_order}"

        # If warehouse is specified, we need to get warehouse-specific quantities
        if warehouse_id:
            # Get warehouse location ID
            warehouses = await self.search_read(
                "stock.warehouse",
                [("id", "=", warehouse_id)],
                ["lot_stock_id"],
                limit=1,
            )
            if warehouses and warehouses[0].get("lot_stock_id"):
                location_id = warehouses[0]["lot_stock_id"][0]

                # For stock filtering, we need to query stock.quant
                # Get all product IDs in the domain first
                all_product_ids = await self._execute(
                    "product.product", "search", domain
                )

                if stock_filter in ["in_stock", "out_of_stock"]:
                    # Get quantities from stock.quant for this location
                    quants = await self.search_read(
                        "stock.quant",
                        [
                            ("product_id", "in", all_product_ids),
                            ("location_id", "child_of", location_id),
                        ],
                        ["product_id", "quantity"],
                    )

                    # Build product -> quantity map
                    product_qty: dict[int, float] = {}
                    for q in quants:
                        pid = q["product_id"][0]
                        product_qty[pid] = product_qty.get(pid, 0) + q["quantity"]

                    # Filter product IDs based on stock filter
                    if stock_filter == "in_stock":
                        filtered_ids = [
                            pid for pid in all_product_ids
                            if product_qty.get(pid, 0) > 0
                        ]
                    else:  # out_of_stock
                        filtered_ids = [
                            pid for pid in all_product_ids
                            if product_qty.get(pid, 0) <= 0
                        ]

                    total = len(filtered_ids)
                    offset = (page - 1) * page_size
                    page_ids = filtered_ids[offset : offset + page_size]

                    if not page_ids:
                        return [], total

                    # Get product details
                    records = await self.read(
                        "product.product",
                        page_ids,
                        ["id", "default_code", "name", "list_price", "categ_id"],
                    )

                    # Add quantity info
                    for r in records:
                        r["qty_available"] = product_qty.get(r["id"], 0)

                    return records, total

                else:
                    # No stock filter, get all products and their quantities
                    total = await self.search_count("product.product", domain)
                    offset = (page - 1) * page_size
                    records = await self.search_read(
                        "product.product",
                        domain,
                        ["id", "default_code", "name", "list_price", "categ_id"],
                        offset=offset,
                        limit=page_size,
                        order=order,
                    )

                    if records:
                        # Get quantities from stock.quant
                        product_ids = [r["id"] for r in records]
                        quants = await self.search_read(
                            "stock.quant",
                            [
                                ("product_id", "in", product_ids),
                                ("location_id", "child_of", location_id),
                            ],
                            ["product_id", "quantity"],
                        )

                        product_qty: dict[int, float] = {}
                        for q in quants:
                            pid = q["product_id"][0]
                            product_qty[pid] = product_qty.get(pid, 0) + q["quantity"]

                        for r in records:
                            r["qty_available"] = product_qty.get(r["id"], 0)

                    return records, total

        # Default behavior (no warehouse filter) - stock filtering using qty_available
        if stock_filter == "in_stock":
            domain.append(("qty_available", ">", 0))
        elif stock_filter == "out_of_stock":
            domain.append(("qty_available", "<=", 0))

        # Get total count
        total = await self.search_count("product.product", domain)

        # Get paginated records
        offset = (page - 1) * page_size
        records = await self.search_read(
            "product.product",
            domain,
            [
                "id",
                "default_code",
                "name",
                "qty_available",
                "list_price",
                "categ_id",
            ],
            offset=offset,
            limit=page_size,
            order=order,
        )

        return records, total

    async def get_sets(self) -> list[dict[str, Any]]:
        """Get all product categories (sets)."""
        return await self.search_read(
            "product.category",
            [],
            ["id", "name", "product_count"],
            order="name",
        )

    async def get_warehouses(self) -> list[dict[str, Any]]:
        """Get all warehouses from Odoo."""
        return await self.search_read(
            "stock.warehouse",
            [],
            ["id", "name", "code", "lot_stock_id"],
            order="name",
        )

    async def get_warehouse_by_name(self, name: str) -> dict[str, Any] | None:
        """Get a warehouse by name."""
        records = await self.search_read(
            "stock.warehouse",
            [("name", "=", name)],
            ["id", "name", "code", "lot_stock_id"],
            limit=1,
        )
        return records[0] if records else None

    async def adjust_stock(
        self,
        product_id: int,
        quantity_change: int,
        warehouse_id: int | None = None,
    ) -> bool:
        """Adjust stock quantity for a product in a specific warehouse."""
        # Get the location ID for this warehouse
        location_id = None
        if warehouse_id:
            warehouses = await self.search_read(
                "stock.warehouse",
                [("id", "=", warehouse_id)],
                ["lot_stock_id"],
                limit=1,
            )
            if warehouses and warehouses[0].get("lot_stock_id"):
                location_id = warehouses[0]["lot_stock_id"][0]

        # Create inventory adjustment
        try:
            # Find or create quant
            quant_domain = [("product_id", "=", product_id)]
            if location_id:
                quant_domain.append(("location_id", "=", location_id))
            else:
                quant_domain.append(("location_id.usage", "=", "internal"))

            quants = await self.search_read(
                "stock.quant",
                quant_domain,
                ["id", "quantity", "location_id"],
                limit=1,
            )

            if quants:
                # Update existing quant
                current_qty = quants[0].get("quantity", 0)
                new_qty = max(0, current_qty + quantity_change)
                await self.write(
                    "stock.quant",
                    [quants[0]["id"]],
                    {"quantity": new_qty},
                )
            else:
                # Get location if not set
                if not location_id:
                    locations = await self.search_read(
                        "stock.location",
                        [("usage", "=", "internal")],
                        ["id"],
                        limit=1,
                    )
                    if locations:
                        location_id = locations[0]["id"]

                if location_id:
                    new_qty = max(0, quantity_change)
                    await self._execute(
                        "stock.quant",
                        "create",
                        {
                            "product_id": product_id,
                            "location_id": location_id,
                            "quantity": new_qty,
                        },
                    )

            return True
        except Exception:
            return False

    async def get_product_quantity_in_warehouse(
        self,
        product_id: int,
        warehouse_id: int,
    ) -> int:
        """Get quantity of a product in a specific warehouse."""
        warehouses = await self.search_read(
            "stock.warehouse",
            [("id", "=", warehouse_id)],
            ["lot_stock_id"],
            limit=1,
        )
        if not warehouses or not warehouses[0].get("lot_stock_id"):
            return 0

        location_id = warehouses[0]["lot_stock_id"][0]
        quants = await self.search_read(
            "stock.quant",
            [
                ("product_id", "=", product_id),
                ("location_id", "child_of", location_id),
            ],
            ["quantity"],
        )

        return int(sum(q.get("quantity", 0) for q in quants))


# Singleton service instance
_odoo_service: OdooService | None = None


@lru_cache
def get_odoo_service() -> OdooService:
    """Get or create the Odoo service singleton."""
    global _odoo_service
    if _odoo_service is None:
        _odoo_service = OdooService(get_settings())
    return _odoo_service


@asynccontextmanager
async def lifespan_odoo():
    """Lifespan context manager for Odoo connection."""
    service = get_odoo_service()
    await service.connect()
    yield service
