"""Authentication router."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from .database import get_failed_attempts, get_recent_login_attempts
from .dependencies import get_current_user, require_admin
from .models import Token, User, UserLogin
from .service import AuthService, get_auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginResponse(BaseModel):
    """Login response with token and user info."""

    token: Token
    user: User


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    credentials: UserLogin,
    auth_service: AuthService = Depends(get_auth_service),
):
    """Login and receive JWT token."""
    # Get client info for logging
    ip_address = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")

    # Check rate limiting first
    failed_attempts = await get_failed_attempts(credentials.username)
    if failed_attempts >= 5:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please try again in 15 minutes.",
        )

    token = await auth_service.login(
        username=credentials.username,
        password=credentials.password,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user info for response
    user = await auth_service.get_current_user(token.access_token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user info",
        )

    return LoginResponse(token=token, user=user)


@router.get("/me", response_model=User)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current authenticated user."""
    return current_user


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """Logout (client should discard token)."""
    # In a more complex setup, we'd invalidate the token server-side
    return {"message": "Logged out successfully"}


@router.get("/verify")
async def verify_token(current_user: User = Depends(get_current_user)):
    """Verify that the current token is valid."""
    return {"valid": True, "user_id": current_user.id, "role": current_user.role}


# Admin-only endpoints
@router.get("/login-attempts", dependencies=[Depends(require_admin)])
async def get_login_attempts(limit: int = 50):
    """Get recent login attempts (admin only)."""
    attempts = await get_recent_login_attempts(limit)
    return {"attempts": attempts}
