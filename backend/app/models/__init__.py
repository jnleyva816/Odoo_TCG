"""Pydantic models for API request/response schemas."""

from .card import Card, CardDetail, CardSearchResult
from .inventory import (
    InventoryItem,
    InventoryResponse,
    StockAdjustment,
    StockFilter,
)
from .label import LabelRequest, LabelResponse
from .portfolio import (
    CostBasisEntry,
    CostBasisInput,
    LiquidityTier,
    PortfolioStats,
    PortfolioSummary,
    PriceMovement,
    TopMover,
)
from .set import SetInfo
from .settings import (
    AppSettings,
    FeatureFlags,
    FeatureFlagUpdate,
    SettingsUpdate,
)
from .vault import (
    Vault,
    VaultCard,
    VaultCreate,
    VaultListItem,
    VaultPublic,
    VaultSettings,
    VaultUpdate,
    VaultVisibility,
)

__all__ = [
    # Card
    "Card",
    "CardDetail",
    "CardSearchResult",
    # Inventory
    "InventoryItem",
    "InventoryResponse",
    "StockAdjustment",
    "StockFilter",
    # Labels
    "LabelRequest",
    "LabelResponse",
    # Sets
    "SetInfo",
    # Settings
    "AppSettings",
    "FeatureFlags",
    "FeatureFlagUpdate",
    "SettingsUpdate",
    # Portfolio (Wall Street Dashboard)
    "CostBasisEntry",
    "CostBasisInput",
    "LiquidityTier",
    "PortfolioStats",
    "PortfolioSummary",
    "PriceMovement",
    "TopMover",
    # Vault (Digital Vault)
    "Vault",
    "VaultCard",
    "VaultCreate",
    "VaultListItem",
    "VaultPublic",
    "VaultSettings",
    "VaultUpdate",
    "VaultVisibility",
]
