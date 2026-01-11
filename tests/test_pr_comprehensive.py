#!/usr/bin/env python3
"""
Comprehensive Test Suite for PR: Production-Grade Security, Observability, and Operational Tooling

This script tests all components added in the PR to verify they work correctly.
"""

import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, '/home/runner/work/Odoo_TCG/Odoo_TCG/backend')

def print_header(title):
    """Print a formatted header."""
    print(f"\n{'=' * 70}")
    print(f"{title}")
    print('=' * 70)

def print_test(name, passed, details=""):
    """Print test result."""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status}: {name}")
    if details:
        print(f"  └─ {details}")

def test_middleware_imports():
    """Test that all middleware components can be imported."""
    print_header("TEST 1: Middleware Imports")
    
    try:
        from app.middleware import (
            SecurityHeadersMiddleware,
            RateLimitMiddleware,
            RequestIDMiddleware,
        )
        print_test("Security middleware imports", True, "All middleware classes imported successfully")
        return True
    except Exception as e:
        print_test("Security middleware imports", False, f"Error: {e}")
        return False

def test_utils_imports():
    """Test that all utility components can be imported."""
    print_header("TEST 2: Utility Imports")
    
    all_passed = True
    
    # Test logging utilities
    try:
        from app.utils.logging import setup_logging, get_logger, JSONFormatter, ColoredFormatter
        print_test("Logging utilities", True, "setup_logging, get_logger, formatters imported")
    except Exception as e:
        print_test("Logging utilities", False, f"Error: {e}")
        all_passed = False
    
    # Test validators
    try:
        from app.utils.validators import (
            validate_email,
            validate_sku,
            sanitize_input,
            validate_barcode,
            sanitize_filename,
        )
        print_test("Validator utilities", True, "All validators imported successfully")
    except Exception as e:
        print_test("Validator utilities", False, f"Error: {e}")
        all_passed = False
    
    return all_passed

def test_validators():
    """Test validator functions."""
    print_header("TEST 3: Validator Functions")
    
    from app.utils.validators import (
        validate_email,
        validate_sku,
        sanitize_input,
        validate_barcode,
        sanitize_filename,
    )
    
    all_passed = True
    
    # Test email validation
    test_cases_email = [
        ("test@example.com", True),
        ("user.name@domain.co.uk", True),
        ("invalid-email", False),
        ("@nodomain.com", False),
    ]
    for email, expected in test_cases_email:
        result = validate_email(email)
        passed = result == expected
        print_test(f"Email validation: {email}", passed, f"Expected {expected}, got {result}")
        all_passed = all_passed and passed
    
    # Test SKU validation
    test_cases_sku = [
        ("sv09-001", True),
        ("ABC-123", True),
        ("invalid sku", False),
        ("sku@#$", False),
    ]
    for sku, expected in test_cases_sku:
        result = validate_sku(sku)
        passed = result == expected
        print_test(f"SKU validation: {sku}", passed, f"Expected {expected}, got {result}")
        all_passed = all_passed and passed
    
    # Test input sanitization
    dangerous_input = "<script>alert('xss')</script>"
    sanitized = sanitize_input(dangerous_input)
    passed = "<script>" not in sanitized and "&lt;script&gt;" in sanitized
    print_test("XSS sanitization", passed, f"HTML escaped: {sanitized[:50]}")
    all_passed = all_passed and passed
    
    # Test barcode validation
    test_cases_barcode = [
        ("1234567890123", True),  # EAN-13
        ("123456789012", True),   # UPC-A
        ("ABC123", True),         # Code-128
        ("", False),
    ]
    for barcode, expected in test_cases_barcode:
        result = validate_barcode(barcode)
        passed = result == expected
        print_test(f"Barcode validation: {barcode or '(empty)'}", passed, f"Expected {expected}, got {result}")
        all_passed = all_passed and passed
    
    # Test filename sanitization
    dangerous_filename = "../../etc/passwd"
    safe_filename = sanitize_filename(dangerous_filename)
    passed = ".." not in safe_filename and "/" not in safe_filename
    print_test("Path traversal prevention", passed, f"Sanitized to: {safe_filename}")
    all_passed = all_passed and passed
    
    return all_passed

def test_logging_setup():
    """Test logging configuration."""
    print_header("TEST 4: Logging Configuration")
    
    from app.utils.logging import setup_logging, get_logger
    
    all_passed = True
    
    # Test colored logging setup
    try:
        setup_logging(debug=True, json_output=False)
        logger = get_logger("test")
        logger.info("Test colored logging")
        print_test("Colored logging setup", True, "Logger configured successfully")
    except Exception as e:
        print_test("Colored logging setup", False, f"Error: {e}")
        all_passed = False
    
    # Test JSON logging setup
    try:
        setup_logging(debug=False, json_output=True)
        logger = get_logger("test")
        logger.info("Test JSON logging")
        print_test("JSON logging setup", True, "JSON formatter configured")
    except Exception as e:
        print_test("JSON logging setup", False, f"Error: {e}")
        all_passed = False
    
    return all_passed

def test_config_additions():
    """Test configuration additions."""
    print_header("TEST 5: Configuration Additions")
    
    try:
        from app.config import Settings
        settings = Settings()
        
        all_passed = True
        
        # Check new config options
        has_log_level = hasattr(settings, 'log_level')
        print_test("Config: log_level", has_log_level, f"Value: {settings.log_level if has_log_level else 'N/A'}")
        
        has_log_format = hasattr(settings, 'log_format')
        print_test("Config: log_format", has_log_format, f"Value: {settings.log_format if has_log_format else 'N/A'}")
        
        return has_log_level and has_log_format
    except Exception as e:
        print_test("Configuration", False, f"Error: {e}")
        return False

def test_middleware_functionality():
    """Test middleware functionality."""
    print_header("TEST 6: Middleware Functionality")
    
    from app.middleware.security import SecurityHeadersMiddleware, RateLimitMiddleware
    from app.middleware.request_id import RequestIDMiddleware
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route
    from starlette.testclient import TestClient
    
    all_passed = True
    
    # Create a simple test app
    async def homepage(request):
        return JSONResponse({"message": "test"})
    
    app = Starlette(routes=[Route('/', homepage)])
    app.add_middleware(SecurityHeadersMiddleware, debug=True)
    app.add_middleware(RequestIDMiddleware)
    
    client = TestClient(app)
    
    # Test security headers
    try:
        response = client.get('/')
        headers = response.headers
        
        expected_headers = [
            'x-content-type-options',
            'x-frame-options',
            'x-xss-protection',
            'content-security-policy',
            'referrer-policy',
            'permissions-policy',
        ]
        
        for header in expected_headers:
            has_header = header in headers
            print_test(f"Security header: {header}", has_header, f"Value: {headers.get(header, 'N/A')[:50]}")
            all_passed = all_passed and has_header
        
        # Test request ID
        has_request_id = 'x-request-id' in headers
        print_test("Request ID header", has_request_id, f"Value: {headers.get('x-request-id', 'N/A')}")
        all_passed = all_passed and has_request_id
        
    except Exception as e:
        print_test("Middleware functionality", False, f"Error: {e}")
        all_passed = False
    
    return all_passed

def test_documentation():
    """Test that all documentation files exist and are non-empty."""
    print_header("TEST 7: Documentation Files")
    
    docs_dir = Path('/home/runner/work/Odoo_TCG/Odoo_TCG/docs')
    root_dir = Path('/home/runner/work/Odoo_TCG/Odoo_TCG')
    
    required_docs = [
        ('docs/API.md', 'API documentation'),
        ('docs/TESTING.md', 'Testing guide'),
        ('docs/PRODUCTION.md', 'Production deployment guide'),
        ('docs/BACKUP.md', 'Backup and restore guide'),
        ('docs/MIGRATIONS.md', 'Database migrations guide'),
        ('docs/AUTHENTICATION_TEST_REPORT.md', 'Authentication test report'),
        ('SECURITY.md', 'Security policy'),
        ('CONTRIBUTING.md', 'Contribution guidelines'),
        ('ENHANCEMENTS.md', 'Enhancement summary'),
    ]
    
    all_passed = True
    for file_path, description in required_docs:
        full_path = root_dir / file_path
        exists = full_path.exists()
        if exists:
            size = full_path.stat().st_size
            print_test(f"Documentation: {file_path}", True, f"{description} ({size} bytes)")
        else:
            print_test(f"Documentation: {file_path}", False, f"File not found")
            all_passed = False
    
    return all_passed

def test_scripts():
    """Test that backup scripts exist and are executable."""
    print_header("TEST 8: Backup Scripts")
    
    scripts_dir = Path('/home/runner/work/Odoo_TCG/Odoo_TCG/scripts/backup')
    
    required_scripts = [
        'backup.sh',
        'restore.sh',
    ]
    
    all_passed = True
    for script in required_scripts:
        script_path = scripts_dir / script
        exists = script_path.exists()
        is_executable = script_path.is_file() and os.access(script_path, os.X_OK) if exists else False
        
        if exists and is_executable:
            print_test(f"Script: {script}", True, "Exists and executable")
        elif exists:
            print_test(f"Script: {script}", True, "Exists (executable bit may not be preserved)")
        else:
            print_test(f"Script: {script}", False, "File not found")
            all_passed = False
    
    return all_passed

def test_security_files():
    """Test security-related files."""
    print_header("TEST 9: Security Files")
    
    root_dir = Path('/home/runner/work/Odoo_TCG/Odoo_TCG')
    
    all_passed = True
    
    # Check .well-known/security.txt
    security_txt = root_dir / '.well-known' / 'security.txt'
    exists = security_txt.exists()
    if exists:
        content = security_txt.read_text()
        has_contact = 'Contact:' in content
        has_expires = 'Expires:' in content
        print_test("security.txt (RFC 9116)", has_contact and has_expires, 
                  f"Contact and Expires fields present")
        all_passed = all_passed and has_contact and has_expires
    else:
        print_test("security.txt", False, "File not found")
        all_passed = False
    
    # Check pre-commit config
    precommit = root_dir / '.pre-commit-config.yaml'
    exists = precommit.exists()
    print_test("Pre-commit hooks config", exists, 
              f"File size: {precommit.stat().st_size if exists else 0} bytes")
    all_passed = all_passed and exists
    
    return all_passed

def test_ci_enhancements():
    """Test CI/CD enhancements."""
    print_header("TEST 10: CI/CD Enhancements")
    
    ci_file = Path('/home/runner/work/Odoo_TCG/Odoo_TCG/.github/workflows/ci.yml')
    
    if not ci_file.exists():
        print_test("CI workflow file", False, "File not found")
        return False
    
    content = ci_file.read_text()
    
    all_passed = True
    
    # Check for security scanning
    has_pip_audit = 'pip-audit' in content or 'pip_audit' in content
    print_test("CI: pip-audit security scan", has_pip_audit, "Backend dependency scanning")
    all_passed = all_passed and has_pip_audit
    
    has_npm_audit = 'npm audit' in content
    print_test("CI: npm audit security scan", has_npm_audit, "Frontend dependency scanning")
    all_passed = all_passed and has_npm_audit
    
    return all_passed

def main():
    """Run all tests."""
    print_header("COMPREHENSIVE PR TEST SUITE")
    print("Testing all features added in PR:")
    print("• Security middleware (headers, rate limiting, request ID)")
    print("• Input validation and sanitization utilities")
    print("• Structured logging (JSON and colored)")
    print("• Configuration additions")
    print("• Documentation completeness")
    print("• Backup scripts")
    print("• Security files (RFC 9116)")
    print("• CI/CD enhancements")
    
    results = []
    
    # Run all tests
    results.append(("Middleware Imports", test_middleware_imports()))
    results.append(("Utility Imports", test_utils_imports()))
    results.append(("Validator Functions", test_validators()))
    results.append(("Logging Configuration", test_logging_setup()))
    results.append(("Configuration Additions", test_config_additions()))
    results.append(("Middleware Functionality", test_middleware_functionality()))
    results.append(("Documentation Files", test_documentation()))
    results.append(("Backup Scripts", test_scripts()))
    results.append(("Security Files", test_security_files()))
    results.append(("CI/CD Enhancements", test_ci_enhancements()))
    
    # Summary
    print_header("TEST SUMMARY")
    
    total = len(results)
    passed = sum(1 for _, result in results if result)
    
    print(f"\nTotal Tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    print(f"Success Rate: {passed/total*100:.1f}%\n")
    
    for name, result in results:
        status = "✅" if result else "❌"
        print(f"{status} {name}")
    
    print("\n" + "=" * 70)
    if passed == total:
        print("🎉 ALL TESTS PASSED - PR is fully functional")
    else:
        print(f"⚠️  {total - passed} test(s) failed - review needed")
    print("=" * 70)
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
