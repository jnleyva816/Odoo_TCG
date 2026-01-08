"""Odoo-based authentication service.

This module authenticates users directly against Odoo's res.users,
eliminating the need for a separate SQLite user database.
"""

import asyncio
import xmlrpc.client
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Any

from jose import JWTError, jwt

from ..config import get_settings
from .models import Token, TokenData, User, UserRole


class OdooAuthService:
    """Authentication service that uses Odoo as the identity provider."""

    def __init__(self):
        settings = get_settings()
        self.odoo_url = settings.odoo_url
        self.odoo_db = settings.odoo_db
        self.secret_key = settings.jwt_secret_key
        self.algorithm = "HS256"
        self.access_token_expire_minutes = settings.jwt_expire_minutes
        self._executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="odoo-auth")
        self._initialized = False

    async def initialize(self):
        """Initialize the auth service."""
        if self._initialized:
            return
        self._initialized = True
        print("🔐 Odoo authentication service initialized")

    def _authenticate_sync(self, username: str, password: str) -> int | None:
        """Synchronously authenticate against Odoo (runs in thread pool)."""
        try:
            common = xmlrpc.client.ServerProxy(
                f"{self.odoo_url}/xmlrpc/2/common",
                allow_none=True,
            )
            uid = common.authenticate(self.odoo_db, username, password, {})
            return uid if uid and uid > 0 else None
        except Exception as e:
            print(f"⚠️ Odoo auth error: {e}")
            return None

    def _get_user_info_sync(self, uid: int, password: str) -> dict[str, Any] | None:
        """Get user information from Odoo (runs in thread pool)."""
        try:
            models = xmlrpc.client.ServerProxy(
                f"{self.odoo_url}/xmlrpc/2/object",
                allow_none=True,
            )
            
            # Fetch user with warehouse and group info
            users = models.execute_kw(
                self.odoo_db,
                uid,
                password,
                "res.users",
                "read",
                [[uid]],
                {
                    "fields": [
                        "id",
                        "login",  # username/email
                        "name",   # display name
                        "email",
                        "active",
                        "property_warehouse_id",  # User's default warehouse
                        "groups_id",  # User groups for role detection
                    ]
                },
            )
            return users[0] if users else None
        except Exception as e:
            print(f"⚠️ Error fetching user info: {e}")
            return None

    def _get_all_warehouses_sync(self, uid: int, password: str) -> list[dict[str, Any]]:
        """Get all warehouses from Odoo (for admins)."""
        try:
            models = xmlrpc.client.ServerProxy(
                f"{self.odoo_url}/xmlrpc/2/object",
                allow_none=True,
            )
            return models.execute_kw(
                self.odoo_db,
                uid,
                password,
                "stock.warehouse",
                "search_read",
                [[]],
                {"fields": ["id", "name", "code"]},
            )
        except Exception as e:
            print(f"⚠️ Error fetching warehouses: {e}")
            return []

    def _check_is_inventory_admin_sync(self, uid: int, password: str) -> bool:
        """Check if user has inventory admin privileges."""
        try:
            models = xmlrpc.client.ServerProxy(
                f"{self.odoo_url}/xmlrpc/2/object",
                allow_none=True,
            )
            
            # Check if user has stock.group_stock_manager group
            # This is the "Inventory > Administrator" group in Odoo
            groups = models.execute_kw(
                self.odoo_db,
                uid,
                password,
                "res.groups",
                "search_read",
                [[("users", "in", [uid]), ("category_id.name", "=", "Inventory")]],
                {"fields": ["name", "full_name"]},
            )
            
            # Check for admin-level groups
            admin_group_names = ["Administrator", "Manager"]
            for group in groups:
                if any(admin in group.get("name", "") for admin in admin_group_names):
                    return True
            
            # Also check for base admin
            admin_groups = models.execute_kw(
                self.odoo_db,
                uid,
                password,
                "res.groups",
                "search_read",
                [[("users", "in", [uid]), ("name", "=", "Access Rights")]],
                {"fields": ["name"]},
            )
            return len(admin_groups) > 0
            
        except Exception as e:
            print(f"⚠️ Error checking admin status: {e}")
            return False

    async def authenticate_user(
        self,
        username: str,
        password: str,
    ) -> tuple[User, str] | None:
        """
        Authenticate a user against Odoo.
        
        Returns tuple of (User, odoo_password) if successful, None otherwise.
        We need to store the password temporarily for subsequent Odoo calls.
        """
        loop = asyncio.get_event_loop()
        
        # Authenticate against Odoo
        uid = await loop.run_in_executor(
            self._executor,
            self._authenticate_sync,
            username,
            password,
        )
        
        if not uid:
            return None

        # Get user info
        user_info = await loop.run_in_executor(
            self._executor,
            self._get_user_info_sync,
            uid,
            password,
        )
        
        if not user_info or not user_info.get("active"):
            return None

        # Check if admin
        is_admin = await loop.run_in_executor(
            self._executor,
            self._check_is_inventory_admin_sync,
            uid,
            password,
        )

        # Get warehouse info
        warehouse_id = None
        warehouse_ids = None
        
        if user_info.get("property_warehouse_id"):
            warehouse_id = user_info["property_warehouse_id"][0]
            warehouse_ids = [warehouse_id]
        
        # If admin, get all warehouses
        if is_admin:
            all_warehouses = await loop.run_in_executor(
                self._executor,
                self._get_all_warehouses_sync,
                uid,
                password,
            )
            warehouse_ids = [w["id"] for w in all_warehouses]
            # Set first warehouse as default if not set
            if not warehouse_id and warehouse_ids:
                warehouse_id = warehouse_ids[0]

        user = User(
            id=uid,
            username=user_info.get("login", username),
            email=user_info.get("email") or user_info.get("login", ""),
            role=UserRole.ADMIN if is_admin else UserRole.USER,
            is_active=user_info.get("active", True),
            warehouse_id=warehouse_id,
            warehouse_ids=warehouse_ids,
            created_at=datetime.utcnow(),  # Odoo doesn't expose this easily
            last_login=datetime.utcnow(),
        )
        
        return user, password

    def create_access_token(
        self,
        user: User,
        odoo_password: str,
        expires_delta: timedelta | None = None,
    ) -> str:
        """Create a JWT access token containing user info and encrypted Odoo password."""
        expire = datetime.utcnow() + (
            expires_delta or timedelta(minutes=self.access_token_expire_minutes)
        )
        
        to_encode = {
            "sub": user.username,
            "user_id": user.id,
            "role": user.role.value,
            "warehouse_id": user.warehouse_id,
            "warehouse_ids": user.warehouse_ids,
            "odoo_pwd": odoo_password,  # Stored in JWT for Odoo API calls
            "exp": expire,
        }
        
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

    def decode_token(self, token: str) -> dict[str, Any] | None:
        """Decode and validate a JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError:
            return None

    async def get_current_user(self, token: str) -> User | None:
        """Get current user from token."""
        payload = self.decode_token(token)
        if not payload:
            return None

        user_id = payload.get("user_id")
        username = payload.get("sub")
        role = payload.get("role", "user")
        warehouse_id = payload.get("warehouse_id")
        warehouse_ids = payload.get("warehouse_ids")
        
        if not user_id or not username:
            return None

        return User(
            id=user_id,
            username=username,
            email=username,  # In Odoo, login is often the email
            role=UserRole(role),
            is_active=True,
            warehouse_id=warehouse_id,
            warehouse_ids=warehouse_ids,
            created_at=datetime.utcnow(),
            last_login=datetime.utcnow(),
        )

    async def get_odoo_password_from_token(self, token: str) -> str | None:
        """Extract Odoo password from token for API calls."""
        payload = self.decode_token(token)
        if not payload:
            return None
        return payload.get("odoo_pwd")

    async def login(
        self,
        username: str,
        password: str,
    ) -> tuple[Token, User] | None:
        """Login and return JWT token + user info."""
        result = await self.authenticate_user(username, password)
        
        if not result:
            return None
        
        user, odoo_password = result
        
        access_token = self.create_access_token(user, odoo_password)
        
        token = Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=self.access_token_expire_minutes * 60,
        )
        
        return token, user

    async def switch_warehouse(self, token: str, warehouse_id: int) -> User | None:
        """Switch user's active warehouse (for admins)."""
        user = await self.get_current_user(token)
        if not user:
            return None
        
        # Verify user has access to this warehouse
        if user.warehouse_ids and warehouse_id not in user.warehouse_ids:
            return None
        
        # Return updated user (the actual switch is handled by updating the token)
        return User(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            warehouse_id=warehouse_id,
            warehouse_ids=user.warehouse_ids,
            created_at=user.created_at,
            last_login=user.last_login,
        )


# Singleton instance
_odoo_auth_service: OdooAuthService | None = None


def get_odoo_auth_service() -> OdooAuthService:
    """Get the Odoo auth service singleton."""
    global _odoo_auth_service
    if _odoo_auth_service is None:
        _odoo_auth_service = OdooAuthService()
    return _odoo_auth_service

