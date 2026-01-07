"""Image serving endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from ..services import OdooService, get_odoo_service, ImageCache

router = APIRouter(prefix="/images", tags=["Images"])

# Global image cache
_image_cache = ImageCache(max_size=1000, ttl_seconds=3600)

# 1x1 transparent PNG for missing images
TRANSPARENT_PNG = bytes([
    0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0x00, 0x00, 0x00, 0x0D,
    0x49, 0x48, 0x44, 0x52, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
    0x08, 0x06, 0x00, 0x00, 0x00, 0x1F, 0x15, 0xC4, 0x89, 0x00, 0x00, 0x00,
    0x0A, 0x49, 0x44, 0x41, 0x54, 0x78, 0x9C, 0x63, 0x00, 0x01, 0x00, 0x00,
    0x05, 0x00, 0x01, 0x0D, 0x0A, 0x2D, 0xB4, 0x00, 0x00, 0x00, 0x00, 0x49,
    0x45, 0x4E, 0x44, 0xAE, 0x42, 0x60, 0x82,
])


@router.get("/{product_id}")
async def get_image(
    product_id: int,
    size: Annotated[str, Query(description="Image size: image_128, image_256, image_512, image_1920")] = "image_256",
    odoo: OdooService = Depends(get_odoo_service),
) -> Response:
    """Get product image by ID."""
    # Validate size parameter
    valid_sizes = {"image_128", "image_256", "image_512", "image_1920"}
    if size not in valid_sizes:
        size = "image_256"

    cache_key = f"{product_id}:{size}"

    # Try cache first
    cached = await _image_cache.get(cache_key)
    if cached:
        return Response(
            content=cached,
            media_type="image/png",
            headers={
                "Cache-Control": "public, max-age=3600",
                "X-Cache": "HIT",
            },
        )

    # Fetch from Odoo
    image_data = await odoo.get_product_image(product_id, size)

    if image_data:
        await _image_cache.set(cache_key, image_data)
        return Response(
            content=image_data,
            media_type="image/png",
            headers={
                "Cache-Control": "public, max-age=3600",
                "X-Cache": "MISS",
            },
        )

    # Return transparent placeholder
    return Response(
        content=TRANSPARENT_PNG,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=60"},
    )


@router.post("/batch")
async def get_images_batch(
    product_ids: list[int],
    size: Annotated[str, Query()] = "image_256",
    odoo: OdooService = Depends(get_odoo_service),
) -> dict[str, str]:
    """Get multiple images at once as base64 strings."""
    import base64

    valid_sizes = {"image_128", "image_256", "image_512", "image_1920"}
    if size not in valid_sizes:
        size = "image_256"

    results: dict[str, str] = {}

    for pid in product_ids[:50]:  # Limit to 50 per batch
        cache_key = f"{pid}:{size}"
        cached = await _image_cache.get(cache_key)

        if cached:
            results[str(pid)] = base64.b64encode(cached).decode()
        else:
            image_data = await odoo.get_product_image(pid, size)
            if image_data:
                await _image_cache.set(cache_key, image_data)
                results[str(pid)] = base64.b64encode(image_data).decode()

    return results


@router.delete("/cache")
async def clear_cache() -> dict:
    """Clear the image cache."""
    size_before = _image_cache.size()
    await _image_cache.clear()
    return {"cleared": size_before, "message": "Image cache cleared"}



