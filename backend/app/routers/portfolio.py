"""Portfolio analytics router - "Wall Street Dashboard".

This provides financial-style analytics for card collections:
- Portfolio summary with value tracking
- Top movers (gainers/losers)
- Value history for charts
- Cost basis tracking (future)

Performance notes:
- Stats are calculated on-demand using Odoo + price_history
- Consider caching for production with high traffic
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth.dependencies import get_current_user
from ..auth.models import User
from ..config import get_settings
from ..models.portfolio import (
    CostBasisEntry,
    CostBasisInput,
    PortfolioStats,
    TopMover,
)
from ..services.portfolio import (
    get_portfolio_stats,
    get_portfolio_value_history,
    get_top_movers,
    get_top_valued_cards,
    get_warehouse_stock,
)

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


def check_feature_enabled():
    """Dependency to check if portfolio dashboard is enabled."""
    settings = get_settings()
    if not settings.feature_portfolio_dashboard:
        raise HTTPException(
            status_code=403,
            detail="Portfolio dashboard feature is not enabled",
        )


@router.get(
    "/stats",
    response_model=PortfolioStats,
    dependencies=[Depends(check_feature_enabled)],
)
async def get_stats(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get portfolio analytics summary.

    Calculates portfolio value and changes using Odoo stock + price_history.

    Includes:
    - Total portfolio value and changes (24h, 7d, 30d)
    - Top gainers and losers
    """
    warehouse_id = current_user.warehouse_id if current_user else None
    stats = await get_portfolio_stats(warehouse_id)
    return stats


@router.get(
    "/history",
    response_model=list[dict],
    dependencies=[Depends(check_feature_enabled)],
)
async def get_value_history(
    days: int = Query(30, ge=7, le=365),
    current_user: Annotated[User | None, Depends(get_current_user)] = None,
):
    """Get portfolio value over time for charting.

    Args:
        days: Number of days of history (7-365)

    Returns:
        List of {date, value} points for the chart
    """
    warehouse_id = current_user.warehouse_id if current_user else None
    history = await get_portfolio_value_history(warehouse_id, days)
    return history


@router.get(
    "/top-movers",
    response_model=list[TopMover],
    dependencies=[Depends(check_feature_enabled)],
)
async def get_movers(
    direction: str = Query("both", pattern="^(up|down|both)$"),
    limit: int = Query(10, ge=1, le=50),
    current_user: Annotated[User | None, Depends(get_current_user)] = None,
):
    """Get cards with biggest price movements in last 24h.

    Args:
        direction: Filter by "up" (gainers), "down" (losers), or "both"
        limit: Number of cards to return (max 50)
    """
    warehouse_id = current_user.warehouse_id if current_user else None
    products = await get_warehouse_stock(warehouse_id)
    gainers, losers = await get_top_movers(products, limit)

    if direction == "up":
        return gainers
    elif direction == "down":
        return losers
    else:
        return gainers + losers


@router.get(
    "/top-cards",
    response_model=list[dict],
    dependencies=[Depends(check_feature_enabled)],
)
async def get_top_cards(
    limit: int = Query(10, ge=1, le=50),
    current_user: Annotated[User | None, Depends(get_current_user)] = None,
):
    """Get top valued cards in stock.

    Returns cards sorted by total value (price * quantity).
    """
    warehouse_id = current_user.warehouse_id if current_user else None
    cards = await get_top_valued_cards(warehouse_id, limit)
    return cards


@router.get(
    "/cost-basis",
    response_model=list[CostBasisEntry],
    dependencies=[Depends(check_feature_enabled)],
)
async def get_cost_basis(
    product_id: int | None = None,
    current_user: Annotated[User | None, Depends(get_current_user)] = None,
):
    """Get cost basis entries for the current user.

    Args:
        product_id: Optional filter by specific product
    """
    # TODO: Implement from database
    return []


@router.post(
    "/cost-basis",
    response_model=CostBasisEntry,
    dependencies=[Depends(check_feature_enabled)],
)
async def add_cost_basis(
    entry: CostBasisInput,
    current_user: Annotated[User | None, Depends(get_current_user)] = None,
):
    """Add a cost basis entry for tracking purchase price.

    Use this to track what you paid for cards so the dashboard
    can calculate unrealized profit.

    Example: You bought a lot of 10 cards for $65
    - product_id: The card ID
    - quantity: 10
    - total_cost: 65.00
    """
    # TODO: Implement database insert
    raise HTTPException(status_code=501, detail="Cost basis tracking not implemented yet")


@router.delete(
    "/cost-basis/{entry_id}",
    dependencies=[Depends(check_feature_enabled)],
)
async def delete_cost_basis(
    entry_id: int,
    current_user: Annotated[User | None, Depends(get_current_user)] = None,
):
    """Delete a cost basis entry."""
    # TODO: Implement database delete
    raise HTTPException(status_code=501, detail="Cost basis tracking not implemented yet")


@router.post(
    "/refresh",
    dependencies=[Depends(check_feature_enabled)],
)
async def refresh_portfolio_stats(
    current_user: Annotated[User | None, Depends(get_current_user)] = None,
):
    """Manually trigger a portfolio stats refresh.

    Stats are calculated on-demand, so this just returns success.
    """
    return {"message": "Portfolio refresh complete", "status": "success"}
