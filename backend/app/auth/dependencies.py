"""Authentication dependencies for FastAPI."""

from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .models import User, UserRole
from .service import AuthService, get_auth_service

# Bearer token security scheme
security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    token: str | None = Query(None, description="JWT token (for img tags)"),
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    """Get the current authenticated user from JWT token.

    Supports both:
    - Authorization: Bearer <token> header
    - ?token=<token> query param (for <img> tags that can't set headers)
    """
    # Try header first, then query param
    auth_token = credentials.credentials if credentials else token

    if not auth_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await auth_service.get_current_user(auth_token)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    auth_service: AuthService = Depends(get_auth_service),
) -> User | None:
    """Get the current user if authenticated, otherwise None."""
    if not credentials:
        return None

    return await auth_service.get_current_user(credentials.credentials)


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Require the current user to be an admin."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user
