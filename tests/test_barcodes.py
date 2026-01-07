"""Tests for barcode generation."""

import pytest

from tcg_automation.commands.barcodes import (
    calculate_ean13_check_digit,
    generate_ean13,
    BARCODE_PREFIX,
)


class TestEAN13CheckDigit:
    """Tests for EAN-13 check digit calculation."""

    def test_check_digit_calculation(self):
        """Test that check digit is calculated correctly."""
        # Known EAN-13: 5901234123457 -> check digit is 7
        first_12 = "590123412345"
        assert calculate_ean13_check_digit(first_12) == "7"

    def test_check_digit_with_zeros(self):
        """Test check digit with all zeros."""
        first_12 = "000000000000"
        assert calculate_ean13_check_digit(first_12) == "0"

    def test_check_digit_invalid_length(self):
        """Test that invalid length raises error."""
        with pytest.raises(ValueError):
            calculate_ean13_check_digit("12345")

    def test_check_digit_non_numeric(self):
        """Test that non-numeric input raises error."""
        with pytest.raises(ValueError):
            calculate_ean13_check_digit("12345678901a")


class TestGenerateEAN13:
    """Tests for full EAN-13 generation."""

    def test_generate_ean13_basic(self):
        """Test basic EAN-13 generation."""
        barcode = generate_ean13(1)
        assert len(barcode) == 13
        assert barcode.isdigit()
        assert barcode.startswith(BARCODE_PREFIX)

    def test_generate_ean13_sequence(self):
        """Test that different sequences produce different barcodes."""
        barcode1 = generate_ean13(1)
        barcode2 = generate_ean13(2)
        assert barcode1 != barcode2

    def test_generate_ean13_valid_check_digit(self):
        """Test that generated barcode has valid check digit."""
        barcode = generate_ean13(12345)
        first_12 = barcode[:12]
        expected_check = calculate_ean13_check_digit(first_12)
        assert barcode[12] == expected_check

    def test_generate_ean13_max_sequence(self):
        """Test with maximum sequence number."""
        barcode = generate_ean13(999_999_999)
        assert len(barcode) == 13
        assert barcode.startswith(BARCODE_PREFIX)

    def test_generate_ean13_invalid_sequence_zero(self):
        """Test that zero sequence raises error."""
        with pytest.raises(ValueError):
            generate_ean13(0)

    def test_generate_ean13_invalid_sequence_negative(self):
        """Test that negative sequence raises error."""
        with pytest.raises(ValueError):
            generate_ean13(-1)

    def test_generate_ean13_invalid_sequence_too_large(self):
        """Test that too large sequence raises error."""
        with pytest.raises(ValueError):
            generate_ean13(1_000_000_000)


class TestBarcodeFormat:
    """Tests for barcode format consistency."""

    def test_barcode_prefix(self):
        """Test that all barcodes use the internal use prefix."""
        for seq in [1, 100, 1000, 999999]:
            barcode = generate_ean13(seq)
            assert barcode.startswith("200"), f"Barcode {barcode} should start with 200"

    def test_sequence_padding(self):
        """Test that sequences are properly padded."""
        barcode = generate_ean13(1)
        # Format: 200 + 9 digits + 1 check = 13 total
        # Sequence 1 should be padded to 000000001
        assert barcode[3:12] == "000000001"

