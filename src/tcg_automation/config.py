"""
Configuration management for TCG Automation.
Uses environment variables with dotenv support.
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Load .env file if present
load_dotenv()


@dataclass
class OdooConfig:
    """Odoo connection configuration."""

    url: str
    db: str
    user: str
    password: str

    @classmethod
    def from_env(cls) -> "OdooConfig":
        """Load configuration from environment variables."""
        return cls(
            url=os.getenv("ODOO_URL", "http://localhost:8069"),
            db=os.getenv("ODOO_DB", ""),
            user=os.getenv("ODOO_USER", ""),
            password=os.getenv("ODOO_PASSWORD", ""),
        )

    def validate(self) -> bool:
        """Check if all required fields are set."""
        return all([self.url, self.db, self.user, self.password])


@dataclass
class ServerConfig:
    """Web server configuration."""

    host: str
    port: int

    @classmethod
    def from_env(cls) -> "ServerConfig":
        return cls(
            host=os.getenv("SERVER_HOST", "0.0.0.0"),
            port=int(os.getenv("SERVER_PORT", "5000")),
        )


@dataclass
class PrinterConfig:
    """Brother QL label printer configuration."""

    ip: str
    port: int
    model: str
    label_size: str
    enabled: bool

    @classmethod
    def from_env(cls) -> "PrinterConfig":
        return cls(
            ip=os.getenv("PRINTER_IP", ""),
            port=int(os.getenv("PRINTER_PORT", "9100")),
            model=os.getenv("PRINTER_MODEL", "QL-800"),
            label_size=os.getenv("PRINTER_LABEL_SIZE", "29"),
            enabled=os.getenv("PRINTER_ENABLED", "false").lower() == "true",
        )

    def validate(self) -> bool:
        """Check if printer is configured."""
        return bool(self.ip) and self.enabled


@dataclass
class Config:
    """Main application configuration."""

    odoo: OdooConfig
    server: ServerConfig
    printer: PrinterConfig

    @classmethod
    def load(cls) -> "Config":
        """Load all configuration from environment."""
        return cls(
            odoo=OdooConfig.from_env(),
            server=ServerConfig.from_env(),
            printer=PrinterConfig.from_env(),
        )


# Global config instance
_config: Config | None = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config.load()
    return _config
