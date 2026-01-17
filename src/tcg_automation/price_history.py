"""Price history database module for CLI.

Records card prices to PostgreSQL for historical tracking.
Gracefully skips if database isn't accessible (e.g., running locally).
"""

import logging
import os
from contextlib import contextmanager
from typing import Any, Generator

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Check if psycopg2 is available
try:
    import psycopg2
    from psycopg2.extras import execute_batch

    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    psycopg2 = None  # type: ignore
    execute_batch = None  # type: ignore


def get_db_config() -> dict[str, Any]:
    """Get PostgreSQL connection config from environment."""
    # Try POSTGRES_HOST first, then extract from ODOO_URL
    postgres_host = os.getenv("POSTGRES_HOST")
    if not postgres_host:
        odoo_url = os.getenv("ODOO_URL", "http://localhost:8069")
        from urllib.parse import urlparse

        parsed = urlparse(odoo_url)
        postgres_host = parsed.hostname or "localhost"

    return {
        "host": postgres_host,
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "database": os.getenv("POSTGRES_DB", "odoo"),
        "user": os.getenv("POSTGRES_USER", "odoo"),
        "password": os.getenv("POSTGRES_PASSWORD", "odoo"),
        "connect_timeout": 5,  # Short timeout for quick failure
    }


@contextmanager
def get_connection() -> Generator[Any, None, None]:
    """Get a database connection."""
    if not PSYCOPG2_AVAILABLE:
        raise RuntimeError("psycopg2 not installed")

    config = get_db_config()
    conn = psycopg2.connect(**config)
    try:
        yield conn
    finally:
        conn.close()


def init_price_history_table() -> bool:
    """Create the price_history table if it doesn't exist."""
    if not PSYCOPG2_AVAILABLE:
        return False

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
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
                """)
            conn.commit()
        return True
    except Exception as e:
        logger.debug(f"Price history DB not accessible: {e}")
        return False


def record_prices_batch(prices: list[dict[str, Any]], source: str = "tcgcsv") -> int:
    """
    Record prices in batch, but only if price changed from last recorded value.
    Avoids redundant data - only stores when price actually changes.
    Returns number of NEW records inserted.
    """
    if not PSYCOPG2_AVAILABLE or not prices:
        return 0

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Get the latest price for each SKU to compare
                skus = [p["sku"] for p in prices]
                cur.execute(
                    """
                    SELECT DISTINCT ON (product_sku)
                        product_sku, price
                    FROM price_history
                    WHERE product_sku = ANY(%s)
                    ORDER BY product_sku, recorded_at DESC
                    """,
                    (skus,),
                )
                last_prices = {row[0]: float(row[1]) for row in cur.fetchall()}

                # Only insert if price changed (or no previous record)
                new_prices = []
                for p in prices:
                    sku = p["sku"]
                    new_price = float(p.get("price", 0))
                    last_price = last_prices.get(sku)

                    # Record if: no previous price OR price changed by more than 1 cent
                    if last_price is None or abs(new_price - last_price) >= 0.01:
                        new_prices.append(
                            (
                                sku,
                                new_price,
                                p.get("low_price"),
                                p.get("mid_price"),
                                p.get("high_price"),
                                p.get("market_price"),
                                source,
                            )
                        )

                if new_prices:
                    execute_batch(
                        cur,
                        """
                        INSERT INTO price_history
                            (product_sku, price, low_price, mid_price, high_price, market_price, source)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        new_prices,
                        page_size=100,
                    )
                    conn.commit()
                    return len(new_prices)
                return 0
    except Exception as e:
        logger.debug(f"Price history recording skipped: {e}")
        return 0


def get_price_history(product_sku: str, limit: int = 30) -> list[dict[str, Any]]:
    """Get price history for a product."""
    if not PSYCOPG2_AVAILABLE:
        return []

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, product_sku, price, low_price, mid_price, high_price,
                           market_price, recorded_at, source
                    FROM price_history
                    WHERE product_sku = %s
                    ORDER BY recorded_at DESC
                    LIMIT %s
                    """,
                    (product_sku, limit),
                )
                columns = [desc[0] for desc in cur.description]
                rows = cur.fetchall()
                return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
