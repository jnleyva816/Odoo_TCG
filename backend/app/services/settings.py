"""Settings service for managing feature flags and app configuration.

Settings are stored in Redis for instant access and runtime changes.
Falls back to environment variables if Redis is unavailable.
"""

import json
import logging
from datetime import datetime

import redis.asyncio as redis

from ..config import get_settings
from ..models.settings import AppSettings, FeatureFlags

logger = logging.getLogger(__name__)

SETTINGS_KEY = "app:settings"


class SettingsService:
    """Service for managing application settings."""

    def __init__(self):
        self._redis: redis.Redis | None = None
        self._config = get_settings()

    async def _get_redis(self) -> redis.Redis | None:
        """Get Redis connection, return None if unavailable."""
        if self._redis is None:
            try:
                self._redis = redis.from_url(
                    self._config.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                )
                # Test connection
                await self._redis.ping()
            except Exception as e:
                logger.warning(f"Redis unavailable for settings: {e}")
                self._redis = None
        return self._redis

    def _get_env_defaults(self) -> FeatureFlags:
        """Get feature flags from environment variables."""
        return FeatureFlags(
            scanner_page=self._config.feature_scanner_page,
            inventory_page=self._config.feature_inventory_page,
            sets_page=self._config.feature_sets_page,
            label_printing=self._config.feature_label_printing,
            portfolio_dashboard=self._config.feature_portfolio_dashboard,
            public_vault=self._config.feature_public_vault,
        )

    async def get_settings(self) -> AppSettings:
        """Get current application settings.

        Priority:
        1. Redis (database settings)
        2. Environment variables (fallback)
        """
        redis_client = await self._get_redis()

        if redis_client:
            try:
                data = await redis_client.get(SETTINGS_KEY)
                if data:
                    settings_dict = json.loads(data)
                    return AppSettings(**settings_dict)
            except Exception as e:
                logger.warning(f"Failed to load settings from Redis: {e}")

        # Fallback to environment defaults
        return AppSettings(features=self._get_env_defaults())

    async def get_features(self) -> FeatureFlags:
        """Get feature flags only."""
        settings = await self.get_settings()
        return settings.features

    async def update_settings(
        self,
        features: dict[str, bool] | None = None,
        site_name: str | None = None,
        maintenance_mode: bool | None = None,
        updated_by: str | None = None,
    ) -> AppSettings:
        """Update application settings.

        Args:
            features: Dict of feature name -> enabled
            site_name: Site display name
            maintenance_mode: Enable maintenance mode
            updated_by: Username making the change
        """
        # Get current settings
        current = await self.get_settings()

        # Update features
        if features:
            current_features = current.features.model_dump()
            for name, enabled in features.items():
                if hasattr(current.features, name):
                    current_features[name] = enabled
            current.features = FeatureFlags(**current_features)

        # Update other settings
        if site_name is not None:
            current.site_name = site_name
        if maintenance_mode is not None:
            current.maintenance_mode = maintenance_mode

        # Update metadata
        current.updated_at = datetime.utcnow()
        current.updated_by = updated_by

        # Save to Redis
        redis_client = await self._get_redis()
        if redis_client:
            try:
                await redis_client.set(
                    SETTINGS_KEY,
                    current.model_dump_json(),
                )
                logger.info(f"Settings updated by {updated_by}")
            except Exception as e:
                logger.error(f"Failed to save settings to Redis: {e}")
                raise

        return current

    async def toggle_feature(
        self,
        name: str,
        enabled: bool,
        updated_by: str | None = None,
    ) -> FeatureFlags:
        """Toggle a single feature flag."""
        settings = await self.update_settings(
            features={name: enabled},
            updated_by=updated_by,
        )
        return settings.features

    async def reset_to_defaults(self) -> AppSettings:
        """Reset all settings to environment defaults."""
        redis_client = await self._get_redis()
        if redis_client:
            await redis_client.delete(SETTINGS_KEY)
        return await self.get_settings()


# Singleton instance
_settings_service: SettingsService | None = None


def get_settings_service() -> SettingsService:
    """Get singleton settings service instance."""
    global _settings_service
    if _settings_service is None:
        _settings_service = SettingsService()
    return _settings_service
