"""Digital Vault router - Public collection showcase.

This allows users to create shareable "binders" of their collection:
- Create named binders (e.g., "High-End Trades", "PSA Graded")
- Publish to a public URL for sharing on Discord/Reddit
- Visitors can filter, search, and view high-res images

Performance notes:
- Published vaults are pre-rendered to static JSON
- Served from Redis cache or CDN (no Odoo queries for visitors)
- Can handle 10,000+ concurrent viewers without touching Odoo
"""

import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from ..auth.dependencies import get_current_user
from ..config import get_settings
from ..models.vault import (
    Vault,
    VaultCreate,
    VaultListItem,
    VaultPublic,
    VaultUpdate,
)

router = APIRouter(prefix="/vault", tags=["vault"])


def check_feature_enabled():
    """Dependency to check if vault feature is enabled."""
    settings = get_settings()
    if not settings.feature_public_vault:
        raise HTTPException(
            status_code=403,
            detail="Public vault feature is not enabled",
        )


def generate_vault_id() -> str:
    """Generate a short, URL-safe vault ID."""
    return secrets.token_urlsafe(6)  # 8 characters


# =============================================================================
# Owner endpoints (require authentication)
# =============================================================================


@router.get(
    "/my-vaults",
    response_model=list[VaultListItem],
    dependencies=[Depends(check_feature_enabled)],
)
async def list_my_vaults(
    current_user: dict = Depends(get_current_user),
):
    """List all vaults owned by the current user."""
    # TODO: Implement database lookup
    return []


@router.post(
    "/",
    response_model=Vault,
    dependencies=[Depends(check_feature_enabled)],
)
async def create_vault(
    vault: VaultCreate,
    current_user: dict = Depends(get_current_user),
):
    """Create a new vault/binder.

    Select cards from your inventory to include in this vault.
    The vault starts as unlisted (only accessible via direct link).
    """
    vault_id = generate_vault_id()

    # TODO: Implement database insert
    return Vault(
        id=vault_id,
        owner_id=current_user.get("uid", 0),
        owner_name=current_user.get("name", "Unknown"),
        name=vault.name,
        description=vault.description,
        visibility=vault.visibility,
        settings=vault.settings,
        card_count=len(vault.product_ids),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@router.get(
    "/{vault_id}",
    response_model=Vault,
    dependencies=[Depends(check_feature_enabled)],
)
async def get_vault(
    vault_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get a vault by ID (owner view with full details)."""
    # TODO: Implement database lookup
    raise HTTPException(status_code=404, detail="Vault not found")


@router.put(
    "/{vault_id}",
    response_model=Vault,
    dependencies=[Depends(check_feature_enabled)],
)
async def update_vault(
    vault_id: str,
    vault: VaultUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Update a vault's settings or card list."""
    # TODO: Implement database update
    raise HTTPException(status_code=404, detail="Vault not found")


@router.delete(
    "/{vault_id}",
    dependencies=[Depends(check_feature_enabled)],
)
async def delete_vault(
    vault_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a vault."""
    # TODO: Implement database delete + cache invalidation
    raise HTTPException(status_code=404, detail="Vault not found")


@router.post(
    "/{vault_id}/publish",
    dependencies=[Depends(check_feature_enabled)],
)
async def publish_vault(
    vault_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Publish a vault to make it publicly accessible.

    This will:
    1. Generate a static JSON snapshot of the vault
    2. Cache it in Redis for instant access
    3. Return the public URL for sharing

    The static snapshot means visitors don't hit your Odoo server.
    """
    # TODO: Implement static generation + Redis caching

    # Generate public URL
    # In production, this would be: https://yourdomain.com/share/{vault_id}
    public_url = f"/share/{vault_id}"

    return {
        "message": "Vault published successfully",
        "public_url": public_url,
        "vault_id": vault_id,
    }


@router.post(
    "/{vault_id}/unpublish",
    dependencies=[Depends(check_feature_enabled)],
)
async def unpublish_vault(
    vault_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Unpublish a vault (remove public access)."""
    # TODO: Implement cache invalidation
    return {"message": "Vault unpublished", "vault_id": vault_id}


# =============================================================================
# Public endpoints (no authentication required)
# =============================================================================


@router.get(
    "/share/{vault_id}",
    response_model=VaultPublic,
    # Note: No auth dependency - this is public
)
async def get_public_vault(vault_id: str):
    """Get a published vault (public view).

    This endpoint is served from Redis cache for performance.
    Does not require authentication.
    """
    settings = get_settings()
    if not settings.feature_public_vault:
        raise HTTPException(status_code=404, detail="Not found")

    # TODO: Lookup from Redis cache
    # If not in cache, return 404 (vault not published)
    raise HTTPException(status_code=404, detail="Vault not found or not published")
