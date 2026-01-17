"""Settings router for admin configuration.

Allows admins to manage feature flags and app settings via UI
instead of environment variables.
"""

from fastapi import APIRouter, Depends, HTTPException

from ..auth.dependencies import get_current_user
from ..models.settings import AppSettings, FeatureFlags, SettingsUpdate
from ..services.settings import get_settings_service

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/features", response_model=FeatureFlags)
async def get_features():
    """Get current feature flags (public endpoint).

    This is called by the frontend to determine which features to show.
    No authentication required.
    """
    service = get_settings_service()
    return await service.get_features()


@router.get("/", response_model=AppSettings)
async def get_settings(
    current_user: dict = Depends(get_current_user),
):
    """Get all application settings (admin only)."""
    service = get_settings_service()
    return await service.get_settings()


@router.put("/", response_model=AppSettings)
async def update_settings(
    updates: SettingsUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Update application settings (admin only).

    Allows updating multiple settings at once:
    - features: Dict of feature_name -> enabled
    - site_name: Display name for the app
    - maintenance_mode: Enable/disable maintenance mode
    """
    service = get_settings_service()

    try:
        return await service.update_settings(
            features=updates.features,
            site_name=updates.site_name,
            maintenance_mode=updates.maintenance_mode,
            updated_by=current_user.get("email", "unknown"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/features/{feature_name}", response_model=FeatureFlags)
async def toggle_feature(
    feature_name: str,
    enabled: bool,
    current_user: dict = Depends(get_current_user),
):
    """Toggle a single feature flag (admin only).

    Valid feature names:
    - scanner_page
    - inventory_page
    - sets_page
    - label_printing
    - portfolio_dashboard
    - public_vault
    """
    valid_features = [
        "scanner_page",
        "inventory_page",
        "sets_page",
        "label_printing",
        "portfolio_dashboard",
        "public_vault",
    ]

    if feature_name not in valid_features:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid feature name. Valid options: {valid_features}",
        )

    service = get_settings_service()

    try:
        return await service.toggle_feature(
            name=feature_name,
            enabled=enabled,
            updated_by=current_user.get("email", "unknown"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset", response_model=AppSettings)
async def reset_settings(
    current_user: dict = Depends(get_current_user),
):
    """Reset all settings to environment defaults (admin only).

    This clears any database-stored settings and reverts to
    the values defined in environment variables.
    """
    service = get_settings_service()
    return await service.reset_to_defaults()
