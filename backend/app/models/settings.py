"""Application settings models for database-stored configuration."""

from datetime import datetime

from pydantic import BaseModel, Field


class FeatureFlags(BaseModel):
    """All feature flags that can be toggled via admin UI."""

    # Core features
    scanner_page: bool = True
    inventory_page: bool = True
    sets_page: bool = False
    label_printing: bool = True

    # Premium features
    portfolio_dashboard: bool = False
    public_vault: bool = False


class AppSettings(BaseModel):
    """Application settings stored in database."""

    # Feature flags
    features: FeatureFlags = Field(default_factory=FeatureFlags)

    # General settings
    site_name: str = "TCG Inventory"
    maintenance_mode: bool = False

    # Metadata
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    updated_by: str | None = None


class FeatureFlagUpdate(BaseModel):
    """Request to update a single feature flag."""

    name: str
    enabled: bool


class SettingsUpdate(BaseModel):
    """Request to update multiple settings."""

    features: dict[str, bool] | None = None
    site_name: str | None = None
    maintenance_mode: bool | None = None

