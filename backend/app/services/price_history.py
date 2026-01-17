"""Price history service for tracking card prices over time."""

import logging
from typing import Any

import asyncpg

from ..config import get_settings

logger = logging.getLogger(__name__)

# Connection pool
_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """Get or create the connection pool."""
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = await asyncpg.create_pool(
            host=settings.postgres_host,
            port=settings.postgres_port,
            database=settings.postgres_db,
            user=settings.postgres_user,
            password=settings.postgres_password,
            min_size=1,
            max_size=10,
        )
    return _pool


async def init_price_history_table() -> None:
    """Create the price_history table if it doesn't exist."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                id SERIAL PRIMARY KEY,
                product_sku VARCHAR(50) NOT NULL,
                price DECIMAL(10,2) NOT NULL,
                low_price DECIMAL(10,2),
                mid_price DECIMAL(10,2),
                high_price DECIMAL(10,2),
                market_price DECIMAL(10,2),
                recorded_at TIMESTAMP DEFAULT NOW(),
                source VARCHAR(50) DEFAULT 'tcgcsv'
            );

            CREATE INDEX IF NOT EXISTS idx_price_history_sku
                ON price_history(product_sku);
            CREATE INDEX IF NOT EXISTS idx_price_history_date
                ON price_history(recorded_at);
            CREATE INDEX IF NOT EXISTS idx_price_history_sku_date
                ON price_history(product_sku, recorded_at DESC);
        """)
        logger.info("Price history table initialized")


async def record_price(
    product_sku: str,
    price: float,
    low_price: float | None = None,
    mid_price: float | None = None,
    high_price: float | None = None,
    market_price: float | None = None,
    source: str = "tcgcsv",
) -> int:
    """
    Record a price point for a product.

    Returns the ID of the inserted record.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO price_history
                (product_sku, price, low_price, mid_price, high_price, market_price, source)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
            """,
            product_sku,
            price,
            low_price,
            mid_price,
            high_price,
            market_price,
            source,
        )
        return row["id"]


async def record_prices_batch(
    prices: list[dict[str, Any]],
    source: str = "tcgcsv",
) -> int:
    """
    Record multiple prices in a single batch.

    Args:
        prices: List of dicts with keys: sku, price, low_price, mid_price, high_price, market_price
        source: Price source identifier

    Returns:
        Number of records inserted
    """
    if not prices:
        return 0

    pool = await get_pool()
    async with pool.acquire() as conn:
        # Prepare data for batch insert
        records = [
            (
                p["sku"],
                p.get("price", 0),
                p.get("low_price"),
                p.get("mid_price"),
                p.get("high_price"),
                p.get("market_price"),
                source,
            )
            for p in prices
        ]

        await conn.executemany(
            """
            INSERT INTO price_history
                (product_sku, price, low_price, mid_price, high_price, market_price, source)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            records,
        )
        return len(records)


async def get_price_history(
    product_sku: str,
    limit: int = 30,
) -> list[dict[str, Any]]:
    """
    Get price history for a product.

    Args:
        product_sku: The product SKU
        limit: Maximum number of records to return

    Returns:
        List of price records, newest first
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, product_sku, price, low_price, mid_price, high_price,
                   market_price, recorded_at, source
            FROM price_history
            WHERE product_sku = $1
            ORDER BY recorded_at DESC
            LIMIT $2
            """,
            product_sku,
            limit,
        )
        return [dict(row) for row in rows]


async def get_latest_prices(
    skus: list[str],
) -> dict[str, dict[str, Any]]:
    """
    Get the latest price for multiple SKUs.

    Returns:
        Dict mapping SKU to latest price record
    """
    if not skus:
        return {}

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT ON (product_sku)
                product_sku, price, low_price, mid_price, high_price,
                market_price, recorded_at
            FROM price_history
            WHERE product_sku = ANY($1)
            ORDER BY product_sku, recorded_at DESC
            """,
            skus,
        )
        return {row["product_sku"]: dict(row) for row in rows}


async def get_price_changes(
    days: int = 1,
    min_change_percent: float = 5.0,
) -> list[dict[str, Any]]:
    """
    Get products with significant price changes.

    Args:
        days: Look back period
        min_change_percent: Minimum price change percentage

    Returns:
        List of products with price changes
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            WITH latest AS (
                SELECT DISTINCT ON (product_sku)
                    product_sku, price, recorded_at
                FROM price_history
                ORDER BY product_sku, recorded_at DESC
            ),
            previous AS (
                SELECT DISTINCT ON (product_sku)
                    product_sku, price as prev_price, recorded_at
                FROM price_history
                WHERE recorded_at < NOW() - INTERVAL '1 day' * $1
                ORDER BY product_sku, recorded_at DESC
            )
            SELECT
                l.product_sku,
                l.price as current_price,
                p.prev_price,
                l.recorded_at,
                ((l.price - p.prev_price) / NULLIF(p.prev_price, 0) * 100) as change_percent
            FROM latest l
            JOIN previous p ON l.product_sku = p.product_sku
            WHERE ABS((l.price - p.prev_price) / NULLIF(p.prev_price, 0) * 100) >= $2
            ORDER BY change_percent DESC
            """,
            days,
            min_change_percent,
        )
        return [dict(row) for row in rows]
