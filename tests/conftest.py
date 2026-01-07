"""Pytest configuration and fixtures."""

import pytest
import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


@pytest.fixture
def sample_sku():
    """Sample SKU for testing."""
    return "sv09-001-holo"


@pytest.fixture
def sample_product():
    """Sample product data for testing."""
    return {
        "id": 1,
        "name": "Pikachu (001)",
        "default_code": "sv09-001",
        "list_price": 5.99,
        "barcode": "2000000000012",
        "qty_available": 3,
    }

