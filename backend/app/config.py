"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Find the project root .env file
_PROJECT_ROOT = Path(__file__).parent.parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE.exists() else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Odoo Connection
    odoo_url: str = "http://localhost:8069"
    odoo_db: str = "odoo"
    odoo_user: str = ""
    odoo_password: str = ""

    # Server
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    debug: bool = True

    # Cache
    image_cache_ttl: int = 3600  # 1 hour
    image_cache_max_size: int = 1000

    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Brother QL Label Printer
    printer_enabled: bool = False
    printer_ip: str = ""
    printer_port: int = 9100
    printer_model: str = "QL-800"
    printer_label_size: str = "29"  # 29mm continuous (1.1")

    # Authentication (REQUIRED - set in .env)
    jwt_secret_key: str = ""  # Generate with: openssl rand -hex 32
    jwt_expire_minutes: int = 1440  # 24 hours
    admin_username: str = ""
    admin_email: str = ""
    admin_password: str = ""

    # Email notifications (optional)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    alert_email: str = ""  # Email to receive security alerts

    # Feature flags - enable/disable features
    feature_sets_page: bool = False  # Sets import page (disabled by default)
    feature_scanner_page: bool = True  # Barcode scanner page
    feature_inventory_page: bool = True  # Inventory management page
    feature_label_printing: bool = True  # Label printing functionality

    # Redis (for caching and Celery broker)
    redis_url: str = "redis://localhost:6379/0"

    # Meilisearch (for fast full-text search)
    meili_url: str = "http://localhost:7700"
    meili_master_key: str = ""  # Set in production!


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
