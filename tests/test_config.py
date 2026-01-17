"""Tests for application configuration."""

import os
import sys
from pathlib import Path
from unittest.mock import patch

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))


class TestFeatureFlags:
    """Tests for feature flag configuration."""

    def test_default_feature_flags(self):
        """Test default values for feature flags."""
        from app.config import Settings

        # Create settings with defaults
        settings = Settings(
            jwt_secret_key="test-secret-key",
            odoo_user="test",
            odoo_password="test",
        )

        assert settings.feature_sets_page is False
        assert settings.feature_scanner_page is True
        assert settings.feature_inventory_page is True
        assert settings.feature_label_printing is True

    def test_feature_flags_from_env(self):
        """Test that feature flags can be set from environment."""
        from app.config import Settings

        with patch.dict(
            os.environ,
            {
                "FEATURE_SETS_PAGE": "true",
                "FEATURE_SCANNER_PAGE": "false",
                "JWT_SECRET_KEY": "test-key",
                "ODOO_USER": "test",
                "ODOO_PASSWORD": "test",
            },
        ):
            settings = Settings()

            assert settings.feature_sets_page is True
            assert settings.feature_scanner_page is False


class TestAuthConfiguration:
    """Tests for authentication configuration."""

    def test_jwt_settings(self):
        """Test JWT configuration settings."""
        from app.config import Settings

        settings = Settings(
            jwt_secret_key="my-super-secret-key-12345",
            jwt_expire_minutes=60,
            odoo_user="test",
            odoo_password="test",
        )

        assert settings.jwt_secret_key == "my-super-secret-key-12345"
        assert settings.jwt_expire_minutes == 60

    def test_admin_settings(self):
        """Test admin user configuration."""
        from app.config import Settings

        settings = Settings(
            jwt_secret_key="test-key",
            admin_username="myadmin",
            admin_email="admin@example.com",
            admin_password="securepass",
            odoo_user="test",
            odoo_password="test",
        )

        assert settings.admin_username == "myadmin"
        assert settings.admin_email == "admin@example.com"
        assert settings.admin_password == "securepass"


class TestPrinterConfiguration:
    """Tests for printer configuration."""

    def test_printer_can_be_disabled(self):
        """Test printer can be disabled."""
        from app.config import Settings

        settings = Settings(
            jwt_secret_key="test-key",
            odoo_user="test",
            odoo_password="test",
            printer_enabled=False,
        )

        assert settings.printer_enabled is False

    def test_printer_settings(self):
        """Test printer configuration options."""
        from app.config import Settings

        settings = Settings(
            jwt_secret_key="test-key",
            printer_enabled=True,
            printer_ip="192.168.1.100",
            printer_port=9100,
            printer_model="QL-800",
            printer_label_size="29",
            odoo_user="test",
            odoo_password="test",
        )

        assert settings.printer_enabled is True
        assert settings.printer_ip == "192.168.1.100"
        assert settings.printer_port == 9100
        assert settings.printer_model == "QL-800"
        assert settings.printer_label_size == "29"


class TestCORSConfiguration:
    """Tests for CORS configuration."""

    def test_default_cors_origins(self):
        """Test default CORS origins."""
        from app.config import Settings

        settings = Settings(
            jwt_secret_key="test-key",
            odoo_user="test",
            odoo_password="test",
        )

        assert "http://localhost:5173" in settings.cors_origins
        assert "http://localhost:3000" in settings.cors_origins


class TestOdooConfiguration:
    """Tests for Odoo connection configuration."""

    def test_odoo_settings(self):
        """Test Odoo connection settings."""
        from app.config import Settings

        settings = Settings(
            jwt_secret_key="test-key",
            odoo_url="http://my-odoo:8069",
            odoo_db="my-database",
            odoo_user="admin@example.com",
            odoo_password="admin-pass",
        )

        assert settings.odoo_url == "http://my-odoo:8069"
        assert settings.odoo_db == "my-database"
        assert settings.odoo_user == "admin@example.com"
        assert settings.odoo_password == "admin-pass"

    def test_odoo_can_be_configured(self):
        """Test Odoo values can be set."""
        from app.config import Settings

        settings = Settings(
            jwt_secret_key="test-key",
            odoo_url="http://custom-server:8069",
            odoo_db="custom-db",
            odoo_user="test",
            odoo_password="test",
        )

        assert settings.odoo_url == "http://custom-server:8069"
        assert settings.odoo_db == "custom-db"

