"""
Odoo XML-RPC client for TCG Automation.
Provides a clean interface for Odoo operations.
"""

import logging
import xmlrpc.client
from typing import Any

from .config import OdooConfig, get_config

logger = logging.getLogger(__name__)


class OdooClient:
    """XML-RPC client for Odoo operations."""

    def __init__(self, config: OdooConfig | None = None):
        self.config = config or get_config().odoo
        self._common: xmlrpc.client.ServerProxy | None = None
        self._models: xmlrpc.client.ServerProxy | None = None
        self._uid: int | None = None

    @property
    def uid(self) -> int:
        """Get authenticated user ID, connecting if needed."""
        if self._uid is None:
            self.connect()
        return self._uid  # type: ignore

    def connect(self) -> bool:
        """Establish connection to Odoo."""
        if not self.config.validate():
            logger.error("Invalid Odoo configuration - missing required fields")
            return False

        logger.info(f"Connecting to Odoo at {self.config.url}...")
        try:
            self._common = xmlrpc.client.ServerProxy(f"{self.config.url}/xmlrpc/2/common")
            self._models = xmlrpc.client.ServerProxy(f"{self.config.url}/xmlrpc/2/object")

            self._uid = self._common.authenticate(
                self.config.db,
                self.config.user,
                self.config.password,
                {}
            )

            if not self._uid:
                logger.error("Odoo authentication failed - check credentials")
                return False

            logger.info(f"Connected to Odoo (User ID: {self._uid})")
            return True

        except Exception as e:
            logger.error(f"Odoo connection failed: {e}")
            return False

    def execute(self, model: str, method: str, *args: Any, **kwargs: Any) -> Any:
        """Execute a method on an Odoo model."""
        if self._models is None:
            self.connect()

        return self._models.execute_kw(  # type: ignore
            self.config.db,
            self.uid,
            self.config.password,
            model,
            method,
            args,
            kwargs
        )

    def search(self, model: str, domain: list) -> list[int]:
        """Search for records matching domain."""
        return self.execute(model, "search", domain)

    def search_read(
        self,
        model: str,
        domain: list,
        fields: list[str] | None = None,
        limit: int | None = None
    ) -> list[dict]:
        """Search and read records in one call."""
        kwargs: dict[str, Any] = {}
        if fields:
            kwargs["fields"] = fields
        if limit:
            kwargs["limit"] = limit
        return self.execute(model, "search_read", domain, **kwargs)

    def read(self, model: str, ids: list[int], fields: list[str] | None = None) -> list[dict]:
        """Read specific records by ID."""
        kwargs = {"fields": fields} if fields else {}
        return self.execute(model, "read", ids, **kwargs)

    def create(self, model: str, values: dict) -> int:
        """Create a new record."""
        result = self.execute(model, "create", [values])
        return result[0] if isinstance(result, list) else result

    def write(self, model: str, ids: list[int], values: dict) -> bool:
        """Update existing records."""
        return self.execute(model, "write", ids, values)

    def unlink(self, model: str, ids: list[int]) -> bool:
        """Delete records."""
        return self.execute(model, "unlink", ids)

    # ==========================================================================
    # Product-specific helpers
    # ==========================================================================

    def get_product_by_sku(self, sku: str) -> dict | None:
        """Get a product by its SKU (default_code)."""
        products = self.search_read(
            "product.product",
            [("default_code", "=", sku)],
            ["id", "name", "default_code", "qty_available", "list_price", "categ_id"],
        )
        return products[0] if products else None

    def get_or_create_category(self, name: str, parent_name: str = "Pokemon") -> int:
        """Get or create a product category."""
        # Find or create parent
        parent_ids = self.search("product.category", [("name", "=", parent_name)])
        if parent_ids:
            parent_id = parent_ids[0]
        else:
            parent_id = self.create("product.category", {"name": parent_name})

        # Find or create child category
        child_ids = self.search(
            "product.category",
            [("name", "=", name), ("parent_id", "=", parent_id)]
        )
        if child_ids:
            return child_ids[0]

        return self.create("product.category", {"name": name, "parent_id": parent_id})

    def add_stock(self, product_id: int, quantity: int = 1) -> bool:
        """Add stock to a product."""
        try:
            # Find stock location
            locations = self.search_read(
                "stock.location",
                [("usage", "=", "internal"), ("name", "=", "Stock")],
                ["id"],
            )
            if not locations:
                locations = self.search_read(
                    "stock.location",
                    [("usage", "=", "internal")],
                    ["id"],
                    limit=1
                )
            if not locations:
                logger.error("No stock location found")
                return False

            location_id = locations[0]["id"]

            # Update or create quant
            quants = self.search_read(
                "stock.quant",
                [("product_id", "=", product_id), ("location_id", "=", location_id)],
                ["id", "quantity"],
            )

            if quants:
                new_qty = quants[0]["quantity"] + quantity
                self.write("stock.quant", [quants[0]["id"]], {"quantity": new_qty})
            else:
                self.create("stock.quant", {
                    "product_id": product_id,
                    "location_id": location_id,
                    "quantity": quantity,
                })

            return True

        except Exception as e:
            logger.error(f"Failed to add stock: {e}")
            return False


# Global client instance
_client: OdooClient | None = None


def get_odoo_client() -> OdooClient:
    """Get the global Odoo client instance."""
    global _client
    if _client is None:
        _client = OdooClient()
    return _client


