#!/usr/bin/env python3
"""
Comprehensive Test Report for PR: Production-Grade Security, Observability, and Operational Tooling

This script verifies all components added in the PR through code analysis,
syntax checking, and file validation (without requiring runtime dependencies).
"""

import ast
from pathlib import Path

# Get project root dynamically
PROJECT_ROOT = Path(__file__).parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"


def check_python_syntax(file_path):
    """Check if Python file has valid syntax."""
    try:
        with open(file_path, "r") as f:
            ast.parse(f.read())
        return True, "Valid Python syntax"
    except SyntaxError as e:
        return False, f"Syntax error: {e}"
    except FileNotFoundError:
        return False, "File not found"
    except Exception as e:
        return False, f"Error: {e}"


def check_file_exists(file_path, description=""):
    """Check if file exists and get its size."""
    path = Path(file_path)
    if path.exists():
        size = path.stat().st_size
        return (
            True,
            f"{description} ({size:,} bytes)" if description else f"Exists ({size:,} bytes)",
        )
    return False, "File not found"


def test_middleware_modules():
    """Test middleware module structure."""
    base_dir = BACKEND_DIR / "app" / "middleware"

    files = [
        ("__init__.py", "Module init"),
        ("security.py", "Security headers and rate limiting"),
        ("request_id.py", "Request ID tracing"),
        ("compression.py", "Response compression"),
    ]

    for filename, description in files:
        file_path = base_dir / filename
        passed, details = check_python_syntax(file_path)
        assert passed, f"Middleware {filename}: {details}"


def test_utils_modules():
    """Test utility module structure."""
    base_dir = BACKEND_DIR / "app" / "utils"

    files = [
        ("__init__.py", "Module init"),
        ("logging.py", "Structured logging (JSON/colored)"),
        ("validators.py", "Input validation and sanitization"),
    ]

    for filename, description in files:
        file_path = base_dir / filename
        passed, details = check_python_syntax(file_path)
        assert passed, f"Utility {filename}: {details}"


def test_main_py_changes():
    """Test changes to main.py."""
    file_path = BACKEND_DIR / "app" / "main.py"

    # Check syntax
    passed, details = check_python_syntax(file_path)
    assert passed, f"main.py syntax: {details}"

    # Check for specific additions
    content = file_path.read_text()

    checks = [
        ("GZipMiddleware", "Response compression"),
        ("SecurityHeadersMiddleware", "Security headers"),
        ("RateLimitMiddleware", "Rate limiting"),
        ("RequestIDMiddleware", "Request ID tracing"),
        ("/api/health/ready", "Readiness probe endpoint"),
        ("graceful", "Graceful shutdown"),
    ]

    for search_term, feature in checks:
        assert search_term in content, f"Feature '{feature}' not found (search: '{search_term}')"


def test_config_changes():
    """Test configuration changes."""
    file_path = BACKEND_DIR / "app" / "config.py"

    # Check syntax
    passed, details = check_python_syntax(file_path)
    assert passed, f"config.py syntax: {details}"

    # Check for new config options
    content = file_path.read_text()

    checks = [
        ("log_level", "Logging level configuration"),
        ("log_format", "Logging format (JSON/colored)"),
    ]

    for config_name, description in checks:
        assert config_name in content, f"Config '{config_name}' not found: {description}"


def test_validators_implementation():
    """Test validator implementations."""
    file_path = BACKEND_DIR / "app" / "utils" / "validators.py"
    assert file_path.exists(), f"validators.py not found at {file_path}"

    content = file_path.read_text()

    validators = [
        ("validate_email", "Email validation"),
        ("validate_sku", "SKU validation"),
        ("sanitize_input", "XSS prevention"),
        ("validate_barcode", "Barcode validation"),
        ("sanitize_filename", "Path traversal prevention"),
    ]

    for func_name, description in validators:
        assert f"def {func_name}" in content, f"Validator '{func_name}' not found: {description}"

    # Check for HTML escaping import
    assert "from html import escape" in content, "HTML escape import not found"


def test_logging_implementation():
    """Test logging implementation."""
    file_path = BACKEND_DIR / "app" / "utils" / "logging.py"
    assert file_path.exists(), f"logging.py not found at {file_path}"

    content = file_path.read_text()

    features = [
        ("JSONFormatter", "JSON log format for production"),
        ("ColoredFormatter", "Colored logs for development"),
        ("setup_logging", "Logging configuration function"),
        ("get_logger", "Logger factory function"),
        ("json.dumps", "JSON serialization"),
    ]

    for feature_name, description in features:
        assert feature_name in content, f"Feature '{feature_name}' not found: {description}"


def test_middleware_implementation():
    """Test middleware implementations."""
    # Test security middleware
    security_file = BACKEND_DIR / "app" / "middleware" / "security.py"
    assert security_file.exists(), f"security.py not found at {security_file}"

    content = security_file.read_text()

    security_features = [
        ("X-Content-Type-Options", "MIME sniffing prevention"),
        ("X-Frame-Options", "Clickjacking protection"),
        ("X-XSS-Protection", "XSS protection"),
        ("Strict-Transport-Security", "HSTS enforcement"),
        ("Content-Security-Policy", "CSP policy"),
        ("Referrer-Policy", "Referrer control"),
        ("Permissions-Policy", "Feature policy"),
        ("RateLimitMiddleware", "Rate limiting class"),
        ("requests_per_minute", "Rate limit configuration"),
    ]

    for feature, description in security_features:
        assert feature in content, f"Security feature '{feature}' not found: {description}"

    # Test request ID middleware
    request_id_file = BACKEND_DIR / "app" / "middleware" / "request_id.py"
    assert request_id_file.exists(), f"request_id.py not found at {request_id_file}"

    content = request_id_file.read_text()

    request_id_features = [
        ("uuid.uuid4", "UUID generation"),
        ("X-Request-ID", "Request ID header"),
        ("request.state.request_id", "Request state attachment"),
    ]

    for feature, description in request_id_features:
        assert feature in content, f"Request ID feature '{feature}' not found: {description}"


def test_documentation():
    """Test documentation files."""
    docs = [
        ("docs/API.md", "API documentation with examples"),
        ("docs/TESTING.md", "Testing guide and strategies"),
        ("docs/PRODUCTION.md", "Production deployment guide"),
        ("docs/BACKUP.md", "Backup and restore procedures"),
        ("docs/MIGRATIONS.md", "Database migration guide"),
        ("docs/AUTHENTICATION_TEST_REPORT.md", "Authentication testing evidence"),
        ("SECURITY.md", "Security policy and disclosure"),
        ("CONTRIBUTING.md", "Contribution guidelines"),
        ("ENHANCEMENTS.md", "PR enhancements summary"),
        (".dependency-security.md", "Dependency security notes"),
    ]

    for file_path, description in docs:
        full_path = PROJECT_ROOT / file_path
        passed, details = check_file_exists(full_path, description)
        assert passed, f"Doc '{file_path}' not found: {description}"


def test_scripts():
    """Test backup scripts."""
    scripts_dir = PROJECT_ROOT / "scripts" / "backup"

    scripts = [
        ("backup.sh", "Automated backup script"),
        ("restore.sh", "Automated restore script"),
    ]

    for script_name, description in scripts:
        script_path = scripts_dir / script_name
        assert script_path.exists(), f"Script '{script_name}' not found"

        # Check if has shebang
        with open(script_path, "r") as f:
            first_line = f.readline()
            assert first_line.startswith("#!"), f"Script '{script_name}' missing shebang"


def test_security_files():
    """Test security-related files."""
    # Check security.txt
    security_txt = PROJECT_ROOT / ".well-known" / "security.txt"
    assert security_txt.exists(), "security.txt not found"

    content = security_txt.read_text()
    assert "Contact:" in content, "security.txt missing Contact field"
    assert "Expires:" in content, "security.txt missing Expires field"

    # Check pre-commit config
    precommit = PROJECT_ROOT / ".pre-commit-config.yaml"
    assert precommit.exists(), "pre-commit-config.yaml not found"

    content = precommit.read_text()
    assert "ruff" in content, "pre-commit missing ruff hook"
    assert "mypy" in content, "pre-commit missing mypy hook"


def test_ci_enhancements():
    """Test CI/CD enhancements."""
    ci_file = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
    assert ci_file.exists(), "CI workflow file not found"

    content = ci_file.read_text()

    enhancements = [
        ("pip-audit", "Backend dependency security scanning"),
        ("npm audit", "Frontend dependency security scanning"),
        ("ruff", "Python linting"),
        ("mypy", "Python type checking"),
    ]

    for search_term, description in enhancements:
        assert search_term in content, f"CI enhancement '{description}' not found (search: '{search_term}')"


def test_readme_updates():
    """Test README updates."""
    readme = PROJECT_ROOT / "README.md"
    assert readme.exists(), "README.md not found"

    content = readme.read_text()

    updates = [
        ("SECURITY.md", "Security policy reference"),
        ("Rate limiting", "Rate limiting documentation"),
        ("OWASP", "Security standards mention"),
        ("docs/", "Documentation links"),
    ]

    for search_term, description in updates:
        assert search_term in content, f"README missing '{description}' (search: '{search_term}')"
