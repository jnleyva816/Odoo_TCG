#!/usr/bin/env python3
"""
Comprehensive Test Suite for PR: Production-Grade Security, Observability, and Operational Tooling

This script tests all components added in the PR to verify they work correctly.
"""

import os
import sys
from pathlib import Path

# Get project root dynamically and add backend to path
PROJECT_ROOT = Path(__file__).parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))


def test_middleware_imports():
    """Test that all middleware components can be imported."""
    from app.middleware import (
        RateLimitMiddleware,
        RequestIDMiddleware,
        SecurityHeadersMiddleware,
    )

    assert SecurityHeadersMiddleware is not None
    assert RateLimitMiddleware is not None
    assert RequestIDMiddleware is not None


def test_utils_imports():
    """Test that all utility components can be imported."""
    # Test logging utilities
    from app.utils.logging import ColoredFormatter, JSONFormatter, get_logger, setup_logging

    assert setup_logging is not None
    assert get_logger is not None
    assert JSONFormatter is not None
    assert ColoredFormatter is not None

    # Test validators
    from app.utils.validators import (
        sanitize_filename,
        sanitize_input,
        validate_barcode,
        validate_email,
        validate_sku,
    )

    assert validate_email is not None
    assert validate_sku is not None
    assert sanitize_input is not None
    assert validate_barcode is not None
    assert sanitize_filename is not None


def test_validators():
    """Test validator functions."""
    from app.utils.validators import (
        sanitize_filename,
        sanitize_input,
        validate_barcode,
        validate_email,
        validate_sku,
    )

    # Test email validation
    assert validate_email("test@example.com") is True
    assert validate_email("user.name@domain.co.uk") is True
    assert validate_email("invalid-email") is False
    assert validate_email("@nodomain.com") is False

    # Test SKU validation
    assert validate_sku("sv09-001") is True
    assert validate_sku("ABC-123") is True
    assert validate_sku("invalid sku") is False
    assert validate_sku("sku@#$") is False

    # Test input sanitization
    dangerous_input = "<script>alert('xss')</script>"
    sanitized = sanitize_input(dangerous_input)
    assert "<script>" not in sanitized
    assert "&lt;script&gt;" in sanitized

    # Test barcode validation
    assert validate_barcode("1234567890123") is True  # EAN-13
    assert validate_barcode("123456789012") is True  # UPC-A
    assert validate_barcode("ABC123") is True  # Code-128
    assert validate_barcode("") is False

    # Test filename sanitization
    dangerous_filename = "../../etc/passwd"
    safe_filename = sanitize_filename(dangerous_filename)
    assert ".." not in safe_filename
    assert "/" not in safe_filename


def test_logging_setup():
    """Test logging configuration."""
    from app.utils.logging import get_logger, setup_logging

    # Test colored logging setup
    setup_logging(debug=True, json_output=False)
    logger = get_logger("test")
    logger.info("Test colored logging")

    # Test JSON logging setup
    setup_logging(debug=False, json_output=True)
    logger = get_logger("test")
    logger.info("Test JSON logging")


def test_config_additions():
    """Test configuration additions."""
    from app.config import Settings

    settings = Settings()

    # Check new config options
    assert hasattr(settings, "log_level"), "Missing log_level config"
    assert hasattr(settings, "log_format"), "Missing log_format config"


def test_middleware_functionality():
    """Test middleware functionality."""
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route
    from starlette.testclient import TestClient

    from app.middleware.request_id import RequestIDMiddleware
    from app.middleware.security import RateLimitMiddleware, SecurityHeadersMiddleware

    # Create a simple test app
    async def homepage(request):
        return JSONResponse({"message": "test"})

    app = Starlette(routes=[Route("/", homepage)])
    app.add_middleware(SecurityHeadersMiddleware, debug=True)
    app.add_middleware(RequestIDMiddleware)

    client = TestClient(app)

    # Test security headers
    response = client.get("/")
    headers = response.headers

    expected_headers = [
        "x-content-type-options",
        "x-frame-options",
        "x-xss-protection",
        "content-security-policy",
        "referrer-policy",
        "permissions-policy",
    ]

    for header in expected_headers:
        assert header in headers, f"Missing security header: {header}"

    # Test request ID
    assert "x-request-id" in headers, "Missing X-Request-ID header"


def test_documentation():
    """Test that all documentation files exist and are non-empty."""
    required_docs = [
        ("docs/API.md", "API documentation"),
        ("docs/TESTING.md", "Testing guide"),
        ("docs/PRODUCTION.md", "Production deployment guide"),
        ("docs/BACKUP.md", "Backup and restore guide"),
        ("docs/MIGRATIONS.md", "Database migrations guide"),
        ("docs/AUTHENTICATION_TEST_REPORT.md", "Authentication test report"),
        ("SECURITY.md", "Security policy"),
        ("CONTRIBUTING.md", "Contribution guidelines"),
        ("ENHANCEMENTS.md", "Enhancement summary"),
    ]

    for file_path, description in required_docs:
        full_path = PROJECT_ROOT / file_path
        assert full_path.exists(), f"Documentation file not found: {file_path} ({description})"
        assert full_path.stat().st_size > 0, f"Documentation file is empty: {file_path}"


def test_scripts():
    """Test that backup scripts exist."""
    scripts_dir = PROJECT_ROOT / "scripts" / "backup"

    required_scripts = [
        "backup.sh",
        "restore.sh",
    ]

    for script in required_scripts:
        script_path = scripts_dir / script
        assert script_path.exists(), f"Script not found: {script}"


def test_security_files():
    """Test security-related files."""
    # Check .well-known/security.txt
    security_txt = PROJECT_ROOT / ".well-known" / "security.txt"
    assert security_txt.exists(), "security.txt not found"

    content = security_txt.read_text()
    assert "Contact:" in content, "security.txt missing Contact field"
    assert "Expires:" in content, "security.txt missing Expires field"

    # Check pre-commit config
    precommit = PROJECT_ROOT / ".pre-commit-config.yaml"
    assert precommit.exists(), "pre-commit-config.yaml not found"


def test_ci_enhancements():
    """Test CI/CD enhancements."""
    ci_file = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
    assert ci_file.exists(), "CI workflow file not found"

    content = ci_file.read_text()

    # Check for security scanning
    assert "pip-audit" in content or "pip_audit" in content, "CI missing pip-audit"
    assert "npm audit" in content, "CI missing npm audit"
