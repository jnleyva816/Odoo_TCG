"""Tests for authentication system."""

import sys
from pathlib import Path

import pytest

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))


class TestPasswordHashing:
    """Tests for password hashing functionality."""

    def test_hash_password(self):
        """Test that passwords are hashed."""
        from app.auth.service import AuthService

        service = AuthService()
        hashed = service.hash_password("test_password")

        assert hashed != "test_password"
        assert len(hashed) > 50  # bcrypt hashes are long

    def test_verify_password_correct(self):
        """Test verifying correct password."""
        from app.auth.service import AuthService

        service = AuthService()
        password = "secure_password_123"
        hashed = service.hash_password(password)

        assert service.verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test verifying incorrect password."""
        from app.auth.service import AuthService

        service = AuthService()
        hashed = service.hash_password("correct_password")

        assert service.verify_password("wrong_password", hashed) is False

    def test_different_hashes_for_same_password(self):
        """Test that same password produces different hashes (salt)."""
        from app.auth.service import AuthService

        service = AuthService()
        password = "test_password"

        hash1 = service.hash_password(password)
        hash2 = service.hash_password(password)

        assert hash1 != hash2  # Different salts


class TestJWTTokens:
    """Tests for JWT token functionality."""

    def test_create_access_token(self):
        """Test creating access token."""
        from app.auth.service import AuthService

        service = AuthService()
        token = service.create_access_token(
            data={"sub": "testuser", "user_id": 1, "role": "user"}
        )

        assert isinstance(token, str)
        assert len(token) > 100  # JWT tokens are long

    def test_decode_valid_token(self):
        """Test decoding a valid token."""
        from app.auth.service import AuthService

        service = AuthService()
        token = service.create_access_token(
            data={"sub": "testuser", "user_id": 1, "role": "admin"}
        )

        token_data = service.decode_token(token)

        assert token_data is not None
        assert token_data.username == "testuser"
        assert token_data.user_id == 1
        assert token_data.role.value == "admin"

    def test_decode_invalid_token(self):
        """Test decoding an invalid token."""
        from app.auth.service import AuthService

        service = AuthService()
        token_data = service.decode_token("invalid.token.here")

        assert token_data is None

    def test_decode_expired_token(self):
        """Test decoding an expired token."""
        from datetime import timedelta

        from app.auth.service import AuthService

        service = AuthService()
        # Create token that expires in negative time (already expired)
        token = service.create_access_token(
            data={"sub": "testuser", "user_id": 1, "role": "user"},
            expires_delta=timedelta(seconds=-1),
        )

        token_data = service.decode_token(token)
        assert token_data is None


class TestUserRoles:
    """Tests for user role functionality."""

    def test_user_role_enum(self):
        """Test UserRole enum values."""
        from app.auth.models import UserRole

        assert UserRole.ADMIN.value == "admin"
        assert UserRole.USER.value == "user"

    def test_token_contains_role(self):
        """Test that tokens contain role information."""
        from app.auth.models import UserRole
        from app.auth.service import AuthService

        service = AuthService()
        token = service.create_access_token(
            data={"sub": "admin", "user_id": 1, "role": "admin"}
        )

        token_data = service.decode_token(token)
        assert token_data.role == UserRole.ADMIN


class TestEAN13CheckDigit:
    """Tests for EAN-13 check digit validation."""

    def test_valid_ean13_format(self):
        """Test that generated EAN-13 is valid format."""
        from tcg_automation.commands.barcodes import generate_ean13

        barcode = generate_ean13(12345)
        assert len(barcode) == 13
        assert barcode.isdigit()

    def test_luhn_checksum(self):
        """Test EAN-13 check digit follows standard algorithm."""
        from tcg_automation.commands.barcodes import calculate_ean13_check_digit

        # Test with known good EAN-13
        # 4006381333931 is a valid EAN-13
        check = calculate_ean13_check_digit("400638133393")
        assert check == "1"


class TestLoginModels:
    """Tests for login-related models."""

    def test_user_login_model(self):
        """Test UserLogin model validation."""
        from app.auth.models import UserLogin

        login = UserLogin(username="testuser", password="password123")
        assert login.username == "testuser"
        assert login.password == "password123"

    def test_user_create_model(self):
        """Test UserCreate model validation."""
        from app.auth.models import UserCreate

        user = UserCreate(
            username="newuser",
            email="test@example.com",
            password="securepass123",
        )
        assert user.username == "newuser"
        assert user.email == "test@example.com"

    def test_user_create_short_password_fails(self):
        """Test that short passwords fail validation."""
        from app.auth.models import UserCreate
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            UserCreate(
                username="user",
                email="test@example.com",
                password="short",  # Less than 8 chars
            )

    def test_user_create_invalid_email_fails(self):
        """Test that invalid emails fail validation."""
        from app.auth.models import UserCreate
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            UserCreate(
                username="user",
                email="not-an-email",
                password="securepass123",
            )


class TestTokenModel:
    """Tests for Token model."""

    def test_token_model(self):
        """Test Token model structure."""
        from app.auth.models import Token

        token = Token(
            access_token="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
            token_type="bearer",
            expires_in=86400,
        )

        assert token.access_token.startswith("eyJ")
        assert token.token_type == "bearer"
        assert token.expires_in == 86400



