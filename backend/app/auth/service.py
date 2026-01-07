"""Authentication service."""

from datetime import datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from ..config import get_settings
from .database import (
    create_user,
    get_failed_attempts,
    get_user_by_id,
    get_user_by_username,
    get_user_count,
    init_db,
    log_login_attempt,
    update_last_login,
)
from .models import Token, TokenData, User, UserRole


class AuthService:
    """Authentication service with JWT and password hashing."""

    def __init__(self):
        settings = get_settings()
        self.secret_key = settings.jwt_secret_key
        self.algorithm = "HS256"
        self.access_token_expire_minutes = settings.jwt_expire_minutes
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self._initialized = False

    async def initialize(self):
        """Initialize the auth service and database."""
        if self._initialized:
            return

        await init_db()

        # Create admin user from environment if no users exist
        user_count = await get_user_count()
        if user_count == 0:
            settings = get_settings()
            if settings.admin_username and settings.admin_password and settings.admin_email:
                await self.create_admin_user(
                    username=settings.admin_username,
                    email=settings.admin_email,
                    password=settings.admin_password,
                )
                print(f"✅ Admin user '{settings.admin_username}' created")
            else:
                print("⚠️  No admin credentials in env")
                print("   Set ADMIN_USERNAME, ADMIN_EMAIL, ADMIN_PASSWORD")

        self._initialized = True

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return self.pwd_context.verify(plain_password, hashed_password)

    def hash_password(self, password: str) -> str:
        """Hash a password."""
        return self.pwd_context.hash(password)

    def create_access_token(
        self,
        data: dict[str, Any],
        expires_delta: timedelta | None = None,
    ) -> str:
        """Create a JWT access token."""
        to_encode = data.copy()
        expire = datetime.utcnow() + (
            expires_delta or timedelta(minutes=self.access_token_expire_minutes)
        )
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

    def decode_token(self, token: str) -> TokenData | None:
        """Decode and validate a JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            username: str | None = payload.get("sub")
            user_id: int | None = payload.get("user_id")
            role: str = payload.get("role", "user")

            if username is None or user_id is None:
                return None

            return TokenData(
                username=username,
                user_id=user_id,
                role=UserRole(role),
            )
        except JWTError:
            return None

    async def authenticate_user(
        self,
        username: str,
        password: str,
        ip_address: str = "",
        user_agent: str = "",
    ) -> User | None:
        """Authenticate a user and return User if successful."""
        # Check for too many failed attempts (rate limiting)
        failed_attempts = await get_failed_attempts(username)
        if failed_attempts >= 5:
            await log_login_attempt(username, ip_address, user_agent, False)
            return None

        user_data = await get_user_by_username(username)

        if not user_data:
            await log_login_attempt(username, ip_address, user_agent, False)
            return None

        if not self.verify_password(password, user_data["hashed_password"]):
            await log_login_attempt(username, ip_address, user_agent, False)
            return None

        if not user_data["is_active"]:
            await log_login_attempt(username, ip_address, user_agent, False)
            return None

        # Success
        await log_login_attempt(username, ip_address, user_agent, True)
        await update_last_login(user_data["id"])

        return User(
            id=user_data["id"],
            username=user_data["username"],
            email=user_data["email"],
            role=UserRole(user_data["role"]),
            is_active=user_data["is_active"],
            created_at=user_data["created_at"],
            last_login=datetime.utcnow(),
        )

    async def login(
        self,
        username: str,
        password: str,
        ip_address: str = "",
        user_agent: str = "",
    ) -> Token | None:
        """Login and return JWT token."""
        user = await self.authenticate_user(username, password, ip_address, user_agent)

        if not user:
            return None

        access_token = self.create_access_token(
            data={
                "sub": user.username,
                "user_id": user.id,
                "role": user.role.value,
            }
        )

        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=self.access_token_expire_minutes * 60,
        )

    async def get_current_user(self, token: str) -> User | None:
        """Get current user from token."""
        token_data = self.decode_token(token)
        if not token_data or not token_data.user_id:
            return None

        user_data = await get_user_by_id(token_data.user_id)
        if not user_data or not user_data["is_active"]:
            return None

        return User(
            id=user_data["id"],
            username=user_data["username"],
            email=user_data["email"],
            role=UserRole(user_data["role"]),
            is_active=user_data["is_active"],
            created_at=user_data["created_at"],
            last_login=user_data["last_login"],
        )

    async def create_admin_user(
        self,
        username: str,
        email: str,
        password: str,
    ) -> int:
        """Create an admin user."""
        hashed_password = self.hash_password(password)
        return await create_user(
            username=username,
            email=email,
            hashed_password=hashed_password,
            role="admin",
        )


# Singleton instance
_auth_service: AuthService | None = None


def get_auth_service() -> AuthService:
    """Get the auth service singleton."""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service
