"""Input validation and sanitization utilities."""

import re
from html import escape


def validate_email(email: str) -> bool:
    """Validate email format using simple regex.

    Args:
        email: Email address to validate

    Returns:
        True if valid, False otherwise
    """
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def validate_sku(sku: str) -> bool:
    """Validate SKU format.

    SKU should contain only alphanumeric characters and hyphens.

    Args:
        sku: SKU to validate

    Returns:
        True if valid, False otherwise
    """
    pattern = r"^[a-zA-Z0-9-]+$"
    return bool(re.match(pattern, sku))


def sanitize_input(text: str, max_length: int = 1000) -> str:
    """Sanitize user input to prevent XSS and injection attacks.

    Args:
        text: Input text to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized text
    """
    if not text:
        return ""

    # Truncate to max length
    text = text[:max_length]

    # Escape HTML entities
    text = escape(text)

    # Remove null bytes
    text = text.replace("\x00", "")

    return text


def validate_barcode(barcode: str) -> bool:
    """Validate barcode format.

    Supports:
    - EAN-13 (13 digits)
    - UPC-A (12 digits)
    - Code-128 (alphanumeric)

    Args:
        barcode: Barcode to validate

    Returns:
        True if valid format, False otherwise
    """
    # EAN-13
    if len(barcode) == 13 and barcode.isdigit():
        return True

    # UPC-A
    if len(barcode) == 12 and barcode.isdigit():
        return True

    # Code-128 (flexible alphanumeric)
    if 1 <= len(barcode) <= 128 and barcode.isprintable():
        return True

    return False


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent directory traversal.

    Args:
        filename: Filename to sanitize

    Returns:
        Safe filename
    """
    # Remove path separators
    filename = filename.replace("/", "_").replace("\\", "_")

    # Remove parent directory references
    filename = filename.replace("..", "_")

    # Keep only safe characters
    filename = re.sub(r"[^a-zA-Z0-9._-]", "_", filename)

    # Limit length
    filename = filename[:255]

    return filename
