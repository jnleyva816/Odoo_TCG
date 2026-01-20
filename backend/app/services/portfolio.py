"""Portfolio analytics service.

Calculates portfolio value and changes using Odoo stock + price_history.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from ..models.portfolio import PortfolioStats, PortfolioSummary, TopMover
from ..services import get_odoo_service
from ..services.price_history import get_latest_prices, get_pool

logger = logging.getLogger(__name__)


async def get_warehouse_stock(warehouse_id: int | None = None) -> list[dict[str, Any]]:
    """Get all products with stock in the warehouse."""
    odoo = get_odoo_service()

    # Get products with stock
    if warehouse_id:
        # Get stock.quant records for this warehouse
        quants = await odoo.search_read(
            "stock.quant",
            [
                ("location_id.warehouse_id", "=", warehouse_id),
                ("quantity", ">", 0),
            ],
            ["product_id", "quantity"],
        )

        # Get unique product IDs
        product_ids = list({q["product_id"][0] for q in quants if q.get("product_id")})
        if not product_ids:
            return []

        # Sum quantities by product
        qty_by_product: dict[int, float] = {}
        for q in quants:
            pid = q["product_id"][0]
            qty_by_product[pid] = qty_by_product.get(pid, 0) + q["quantity"]

        # Get product details
        products = await odoo.read(
            "product.product",
            product_ids,
            ["id", "name", "default_code", "list_price", "categ_id"],
        )

        # Add quantities
        for p in products:
            p["qty_available"] = qty_by_product.get(p["id"], 0)

        return products
    else:
        # Get all products with stock
        products = await odoo.search_read(
            "product.product",
            [("qty_available", ">", 0), ("default_code", "!=", False)],
            ["id", "name", "default_code", "list_price", "qty_available", "categ_id"],
        )
        return products


async def calculate_portfolio_value(
    products: list[dict], price_date: datetime | None = None
) -> Decimal:
    """
    Calculate total portfolio value.

    Args:
        products: List of products with qty_available and default_code
        price_date: If provided, use historical prices from this date

    Returns:
        Total portfolio value
    """
    if not products:
        return Decimal("0")

    if price_date is None:
        # Use current prices from Odoo
        total = sum(
            Decimal(str(p.get("list_price", 0))) * Decimal(str(p.get("qty_available", 0)))
            for p in products
        )
        return total

    # Use historical prices from price_history
    try:
        skus = [p.get("default_code", "") for p in products if p.get("default_code")]
        historical_prices = await get_prices_at_date(skus, price_date)

        total = Decimal("0")
        for p in products:
            sku = p.get("default_code", "")
            qty = Decimal(str(p.get("qty_available", 0)))
            price = historical_prices.get(sku, Decimal(str(p.get("list_price", 0))))
            total += price * qty

        return total
    except Exception:
        # Price history DB not available - use current prices
        return sum(
            Decimal(str(p.get("list_price", 0))) * Decimal(str(p.get("qty_available", 0)))
            for p in products
        )


async def get_prices_at_date(skus: list[str], target_date: datetime) -> dict[str, Decimal]:
    """Get historical prices for SKUs at a specific date."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT ON (product_sku)
                    product_sku, price
                FROM price_history
                WHERE product_sku = ANY($1)
                  AND recorded_at <= $2
                ORDER BY product_sku, recorded_at DESC
                """,
                skus,
                target_date,
            )
            return {row["product_sku"]: Decimal(str(row["price"])) for row in rows}
    except Exception:
        # Price history DB not available - will use current prices as fallback
        return {}


async def get_portfolio_stats(warehouse_id: int | None = None) -> PortfolioStats:
    """
    Calculate complete portfolio statistics.

    Returns portfolio value, changes over time, and top movers.
    """
    # Get products with stock
    products = await get_warehouse_stock(warehouse_id)

    if not products:
        return PortfolioStats(
            summary=PortfolioSummary(
                total_cards=0,
                total_unique_cards=0,
                total_value=Decimal("0"),
            ),
            top_gainers=[],
            top_losers=[],
            recent_price_changes=[],
        )

    # Calculate current value
    total_cards = sum(int(p.get("qty_available", 0)) for p in products)
    total_unique = len(products)
    current_value = await calculate_portfolio_value(products)

    # Calculate historical values
    now = datetime.utcnow()
    value_24h_ago = await calculate_portfolio_value(products, now - timedelta(hours=24))
    value_7d_ago = await calculate_portfolio_value(products, now - timedelta(days=7))
    value_30d_ago = await calculate_portfolio_value(products, now - timedelta(days=30))

    # Calculate changes
    change_24h = current_value - value_24h_ago
    change_7d = current_value - value_7d_ago
    change_30d = current_value - value_30d_ago

    change_24h_pct = float(change_24h / value_24h_ago * 100) if value_24h_ago else 0
    change_7d_pct = float(change_7d / value_7d_ago * 100) if value_7d_ago else 0
    change_30d_pct = float(change_30d / value_30d_ago * 100) if value_30d_ago else 0

    # Get top movers (cards with biggest price changes in last 24h)
    top_gainers, top_losers = await get_top_movers(products)

    summary = PortfolioSummary(
        total_cards=total_cards,
        total_unique_cards=total_unique,
        total_value=current_value,
        value_24h_ago=value_24h_ago,
        value_7d_ago=value_7d_ago,
        value_30d_ago=value_30d_ago,
        change_24h=change_24h,
        change_7d=change_7d,
        change_30d=change_30d,
        change_24h_percent=round(change_24h_pct, 2),
        change_7d_percent=round(change_7d_pct, 2),
        change_30d_percent=round(change_30d_pct, 2),
        calculated_at=now,
    )

    return PortfolioStats(
        summary=summary,
        top_gainers=top_gainers,
        top_losers=top_losers,
        recent_price_changes=[],
    )


async def get_top_movers(
    products: list[dict], limit: int = 5
) -> tuple[list[TopMover], list[TopMover]]:
    """Get top gainers and losers from the portfolio."""
    if not products:
        return [], []

    skus = [p.get("default_code", "") for p in products if p.get("default_code")]
    now = datetime.utcnow()

    # Get current and 24h ago prices
    current_prices = {p["default_code"]: p["list_price"] for p in products if p.get("default_code")}
    historical_prices = await get_prices_at_date(skus, now - timedelta(hours=24))

    # Calculate changes
    movers = []
    for p in products:
        sku = p.get("default_code", "")
        if not sku:
            continue

        current = Decimal(str(p.get("list_price", 0)))
        previous = historical_prices.get(sku, current)

        if previous == 0:
            continue

        change = current - previous
        pct_change = float(change / previous * 100) if previous else 0

        if abs(pct_change) >= 1:  # Only include if >= 1% change
            categ = p.get("categ_id")
            set_name = categ[1] if isinstance(categ, (list, tuple)) else ""

            movers.append(
                TopMover(
                    product_id=p["id"],
                    name=p.get("name", ""),
                    sku=sku,
                    set_name=set_name,
                    image_url=None,
                    current_price=current,
                    price_change_24h=change,
                    percent_change_24h=round(pct_change, 2),
                    quantity_owned=int(p.get("qty_available", 0)),
                    direction="up" if change > 0 else "down",
                )
            )

    # Sort and split
    gainers = sorted([m for m in movers if m.direction == "up"], key=lambda x: x.percent_change_24h, reverse=True)[:limit]
    losers = sorted([m for m in movers if m.direction == "down"], key=lambda x: x.percent_change_24h)[:limit]

    return gainers, losers


async def get_portfolio_value_history(
    warehouse_id: int | None = None, days: int = 30
) -> list[dict]:
    """
    Get portfolio value over time for charting.

    Returns list of {date, value} points.
    """
    products = await get_warehouse_stock(warehouse_id)
    if not products:
        return []

    # Check if price history DB is available by trying one query
    now = datetime.utcnow()
    test_skus = [p.get("default_code", "") for p in products[:1] if p.get("default_code")]
    test_prices = await get_prices_at_date(test_skus, now - timedelta(days=1))

    # If no historical prices available, return just today's value
    if not test_prices:
        current_value = await calculate_portfolio_value(products)
        return [{
            "date": now.strftime("%Y-%m-%d"),
            "value": float(current_value),
        }]

    history = []

    # Get value for each day
    for i in range(days, -1, -1):
        date = now - timedelta(days=i)
        value = await calculate_portfolio_value(products, date)
        history.append({
            "date": date.strftime("%Y-%m-%d"),
            "value": float(value),
        })

    return history


async def get_top_valued_cards(
    warehouse_id: int | None = None, limit: int = 10
) -> list[dict]:
    """
    Get top valued cards in stock, sorted by total value (price * quantity).

    Returns list of cards with their value info.
    """
    products = await get_warehouse_stock(warehouse_id)
    if not products:
        return []

    # Calculate total value for each card
    valued_cards = []
    for p in products:
        price = float(p.get("list_price", 0))
        qty = int(p.get("qty_available", 0))
        total_value = price * qty

        if total_value > 0:
            categ = p.get("categ_id")
            set_name = categ[1] if isinstance(categ, (list, tuple)) else ""

            valued_cards.append({
                "product_id": p["id"],
                "name": p.get("name", ""),
                "sku": p.get("default_code", ""),
                "set_name": set_name,
                "price": price,
                "quantity": qty,
                "total_value": total_value,
            })

    # Sort by total value descending
    valued_cards.sort(key=lambda x: x["total_value"], reverse=True)

    return valued_cards[:limit]

