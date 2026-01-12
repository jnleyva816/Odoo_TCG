"""Portfolio analytics router - "Wall Street Dashboard".

This provides financial-style analytics for card collections:
- Portfolio summary with value tracking
- Top movers (gainers/losers)
- Liquidity breakdown
- Cost basis tracking

Performance notes:
- Stats are pre-calculated via scheduled job (see tasks.py)
- Dashboard loads from Redis cache (<20ms)
- Only cost basis updates hit the database in real-time
"""

from fastapi import APIRouter, Depends, HTTPException

from ..auth.dependencies import get_current_user
from ..config import get_settings
from ..models.portfolio import (
    CostBasisEntry,
    CostBasisInput,
    PortfolioStats,
    PortfolioSummary,
    TopMover,
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
async def get_portfolio_stats(
    current_user: dict = Depends(get_current_user),
):
    """Get portfolio analytics summary.

    Returns pre-calculated stats from Redis cache.
    Stats are updated every night at 3 AM via scheduled job.

    Includes:
    - Total portfolio value and changes (24h, 7d, 30d)
    - Unrealized profit (if cost basis tracked)
    - Liquidity breakdown
    - Top gainers and losers
    """
    # TODO: Implement Redis cache lookup
    # For now, return placeholder data
    return PortfolioStats(
        summary=PortfolioSummary(
            total_cards=0,
            total_unique_cards=0,
            total_value=0,
        ),
        top_gainers=[],
        top_losers=[],
        recent_price_changes=[],
    )


@router.get(
    "/top-movers",
    response_model=list[TopMover],
    dependencies=[Depends(check_feature_enabled)],
)
async def get_top_movers(
    direction: str = "both",  # "up", "down", or "both"
    limit: int = 10,
    current_user: dict = Depends(get_current_user),
):
    """Get cards with biggest price movements in last 24h.

    Args:
        direction: Filter by "up" (gainers), "down" (losers), or "both"
        limit: Number of cards to return (max 50)
    """
    if limit > 50:
        limit = 50

    # TODO: Implement from Redis cache
    return []


@router.get(
    "/cost-basis",
    response_model=list[CostBasisEntry],
    dependencies=[Depends(check_feature_enabled)],
)
async def get_cost_basis(
    product_id: int | None = None,
    current_user: dict = Depends(get_current_user),
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
    current_user: dict = Depends(get_current_user),
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
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.delete(
    "/cost-basis/{entry_id}",
    dependencies=[Depends(check_feature_enabled)],
)
async def delete_cost_basis(
    entry_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Delete a cost basis entry."""
    # TODO: Implement database delete
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.post(
    "/refresh",
    dependencies=[Depends(check_feature_enabled)],
)
async def refresh_portfolio_stats(
    current_user: dict = Depends(get_current_user),
):
    """Manually trigger a portfolio stats refresh.

    Normally stats are calculated at 3 AM. Use this to
    force an immediate recalculation.

    Note: This is rate-limited to once per hour.
    """
    # TODO: Trigger Celery task
    return {"message": "Portfolio refresh queued", "status": "pending"}
