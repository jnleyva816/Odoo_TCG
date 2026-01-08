"""Authentication router using Odoo as identity provider."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from .dependencies import get_current_user, require_admin
from .models import Token, User, UserLogin, UserRole
from .odoo_auth import OdooAuthService, get_odoo_auth_service
from ..services import OdooService, get_odoo_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginResponse(BaseModel):
    """Login response with token and user info."""

    token: Token
    user: User


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    credentials: UserLogin,
    auth_service: OdooAuthService = Depends(get_odoo_auth_service),
):
    """Login using Odoo credentials and receive JWT token."""
    result = await auth_service.login(
        username=credentials.username,
        password=credentials.password,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Odoo username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token, user = result
    return LoginResponse(token=token, user=user)


@router.get("/me", response_model=User)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current authenticated user."""
    return current_user


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """Logout (client should discard token)."""
    return {"message": "Logged out successfully"}


@router.get("/verify")
async def verify_token(current_user: User = Depends(get_current_user)):
    """Verify that the current token is valid."""
    return {
        "valid": True,
        "user_id": current_user.id,
        "role": current_user.role,
        "warehouse_id": current_user.warehouse_id,
    }


# ============================================================
# Warehouse Management
# ============================================================


class WarehouseInfo(BaseModel):
    """Warehouse information."""

    id: int
    name: str
    code: str


class SwitchWarehouseRequest(BaseModel):
    """Request to switch active warehouse."""

    warehouse_id: int


class SwitchWarehouseResponse(BaseModel):
    """Response after switching warehouse."""

    success: bool
    message: str
    warehouse_id: int
    new_token: str  # New JWT with updated warehouse


@router.get("/warehouses", response_model=list[WarehouseInfo])
async def get_warehouses(
    current_user: User = Depends(get_current_user),
    odoo: OdooService = Depends(get_odoo_service),
):
    """Get available warehouses for current user.

    - Admins see all warehouses they have access to (warehouse_ids)
    - Regular users only see their assigned warehouse
    """
    all_warehouses = await odoo.get_warehouses()

    # If admin with warehouse_ids, filter to allowed warehouses
    if current_user.role == UserRole.ADMIN and current_user.warehouse_ids:
        warehouses = [
            w for w in all_warehouses if w["id"] in current_user.warehouse_ids
        ]
    elif current_user.warehouse_id:
        # Regular user - only their warehouse
        warehouses = [w for w in all_warehouses if w["id"] == current_user.warehouse_id]
    else:
        # Fallback - show all (for backwards compatibility)
        warehouses = all_warehouses

    return [
        WarehouseInfo(id=w["id"], name=w["name"], code=w.get("code", ""))
        for w in warehouses
    ]


@router.post("/switch-warehouse", response_model=SwitchWarehouseResponse)
async def switch_warehouse(
    request: Request,
    switch_request: SwitchWarehouseRequest,
    current_user: User = Depends(require_admin),
    auth_service: OdooAuthService = Depends(get_odoo_auth_service),
):
    """Switch active warehouse (admin only).

    Returns a new JWT token with the updated warehouse.
    """
    # Verify admin has access to this warehouse
    if current_user.warehouse_ids and switch_request.warehouse_id not in current_user.warehouse_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this warehouse",
        )

    # Get the old token to extract the Odoo password
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        old_token = auth_header[7:]
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization token",
        )

    # Get Odoo password from old token
    odoo_password = await auth_service.get_odoo_password_from_token(old_token)
    if not odoo_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    # Create updated user with new warehouse
    updated_user = User(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        role=current_user.role,
        is_active=current_user.is_active,
        warehouse_id=switch_request.warehouse_id,
        warehouse_ids=current_user.warehouse_ids,
        created_at=current_user.created_at,
        last_login=current_user.last_login,
    )

    # Create new token with updated warehouse
    new_token = auth_service.create_access_token(updated_user, odoo_password)

    return SwitchWarehouseResponse(
        success=True,
        message=f"Switched to warehouse {switch_request.warehouse_id}",
        warehouse_id=switch_request.warehouse_id,
        new_token=new_token,
    )
