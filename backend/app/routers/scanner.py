"""
Scanner API endpoints for Pokemon card detection and identification.

This module provides endpoints for:
- Scanning images to detect and identify Pokemon cards
- Real-time webcam scanning via WebSocket
- Scanner status and configuration
"""

import asyncio
import base64
import io
import logging
from typing import Annotated, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from PIL import Image
from pydantic import BaseModel, Field

from ..auth.dependencies import get_current_user
from ..services.scanner import get_scanner_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scanner", tags=["scanner"])


# ============================================================================
# Pydantic Models
# ============================================================================


class ScannerStatus(BaseModel):
    """Scanner service status."""
    ready: bool
    detector_loaded: bool
    matcher_loaded: bool
    hash_count: int
    message: str
    mode: str = "hashing"  # "embeddings" or "hashing"
    embedding_count: int = 0


class ScanRequest(BaseModel):
    """Request body for base64 image scanning."""
    image: str = Field(..., description="Base64 encoded image")
    detect_only: bool = Field(False, description="Only detect, don't identify")


class ScanResponse(BaseModel):
    """Response from scanning an image."""
    success: bool
    result: dict
    message: str = ""


class CardIdentifyRequest(BaseModel):
    """Request to identify a pre-cropped card image."""
    image: str = Field(..., description="Base64 encoded cropped card image")


class CardIdentifyResponse(BaseModel):
    """Response from card identification."""
    success: bool
    matches: list[dict]
    message: str = ""


class QuickAddRequest(BaseModel):
    """Request to scan and add card to inventory."""
    image: str = Field(..., description="Base64 encoded image")
    warehouse_id: Optional[int] = Field(None, description="Target warehouse ID")
    quantity: int = Field(1, ge=1, le=100, description="Quantity to add")
    confirm_match: bool = Field(
        False,
        description="If True, automatically add best match without confirmation"
    )


class QuickAddResponse(BaseModel):
    """Response from quick add operation."""
    success: bool
    card_added: bool
    card_info: Optional[dict] = None
    scan_result: dict
    message: str = ""


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/status", response_model=ScannerStatus)
async def get_scanner_status():
    """
    Get scanner service status.

    Returns whether the scanner is ready and component status.
    Mode indicates which matching algorithm is being used:
    - "embeddings": SOTA neural embedding + FAISS (more accurate)
    - "hashing": Perceptual hashing fallback
    """
    scanner = get_scanner_service()
    status_info = await scanner.initialize()

    mode = status_info.get("mode", "hashing")
    message = "Scanner ready"
    if status_info["initialized"]:
        if mode == "embeddings":
            count = status_info.get('embedding_count', 0)
            message = f"Scanner ready (SOTA mode: {count} embeddings)"
        else:
            message = f"Scanner ready (hash mode: {status_info['hash_count']} hashes)"
    else:
        message = "Scanner not fully initialized"

    return ScannerStatus(
        ready=status_info["initialized"],
        detector_loaded=status_info["detector"],
        matcher_loaded=status_info["matcher"],
        hash_count=status_info["hash_count"],
        message=message,
        mode=mode,
        embedding_count=status_info.get("embedding_count", 0),
    )


@router.post("/scan", response_model=ScanResponse)
async def scan_image(
    file: Annotated[UploadFile, File(description="Image file to scan")],
    detect_only: Annotated[bool, Form()] = False,
):
    """
    Scan an uploaded image for Pokemon cards.

    This performs two-stage detection:
    1. YOLO model detects card bounding boxes
    2. Perceptual hashing identifies each detected card

    Args:
        file: Image file (JPEG, PNG, WebP)
        detect_only: If True, only detect cards without identification

    Returns:
        Scan results with detections and matches
    """
    scanner = get_scanner_service()

    if not scanner.is_ready:
        await scanner.initialize()

    # Validate file type
    if file.content_type not in ["image/jpeg", "image/png", "image/webp"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type: {file.content_type}. Use JPEG, PNG, or WebP.",
        )

    # Read and process image
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))

        # Scan
        result = await scanner.scan_image(image, detect_only=detect_only)

        return ScanResponse(
            success=True,
            result=result.to_dict(),
        )

    except Exception as e:
        logger.exception("Scan failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scan failed: {str(e)}",
        )


@router.post("/scan/base64", response_model=ScanResponse)
async def scan_base64_image(request: ScanRequest):
    """
    Scan a base64-encoded image for Pokemon cards.

    Useful for webcam/canvas data where the image is already encoded.
    """
    scanner = get_scanner_service()

    if not scanner.is_ready:
        await scanner.initialize()

    try:
        # Decode base64
        # Handle data URL format: data:image/jpeg;base64,/9j/4AAQ...
        image_data = request.image
        if "," in image_data:
            image_data = image_data.split(",")[1]

        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))

        # Scan
        result = await scanner.scan_image(image, detect_only=request.detect_only)

        return ScanResponse(
            success=True,
            result=result.to_dict(),
        )

    except Exception as e:
        logger.exception("Base64 scan failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scan failed: {str(e)}",
        )


@router.post("/identify", response_model=CardIdentifyResponse)
async def identify_card(request: CardIdentifyRequest):
    """
    Identify a pre-cropped card image.

    Use this when you've already cropped the card from an image
    (e.g., from detection results) and just need identification.
    """
    scanner = get_scanner_service()

    if not scanner.is_ready:
        await scanner.initialize()

    try:
        # Decode base64
        image_data = request.image
        if "," in image_data:
            image_data = image_data.split(",")[1]

        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))

        # Identify
        matches = await scanner.identify_card(image)

        return CardIdentifyResponse(
            success=True,
            matches=[m.to_dict() for m in matches],
        )

    except Exception as e:
        logger.exception("Identify failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Identification failed: {str(e)}",
        )


@router.post("/quick-add", response_model=QuickAddResponse)
async def quick_add_card(
    request: QuickAddRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Scan an image and optionally add the detected card to inventory.

    This is a convenience endpoint that combines scanning and inventory update.

    Flow:
    1. Scan image to detect and identify card
    2. If confirm_match=True and a high-confidence match is found, add to inventory
    3. Otherwise, return scan results for user confirmation
    """
    from ..services import get_odoo_service

    scanner = get_scanner_service()
    odoo = get_odoo_service()

    if not scanner.is_ready:
        await scanner.initialize()

    try:
        # Decode and scan
        image_data = request.image
        if "," in image_data:
            image_data = image_data.split(",")[1]

        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))

        result = await scanner.scan_image(image)

        response = QuickAddResponse(
            success=True,
            card_added=False,
            scan_result=result.to_dict(),
        )

        # Check if we have a match
        if result.matches:
            best_match = result.matches[0]
            response.card_info = best_match.to_dict()

            # Auto-add if confirmed and high confidence
            if request.confirm_match and best_match.confidence >= 0.85:
                # card_id is already the Odoo product ID
                success = await odoo.adjust_stock(
                    product_id=best_match.card_id,
                    quantity_change=request.quantity,
                    warehouse_id=request.warehouse_id,
                )

                if success:
                    response.card_added = True
                    response.message = (
                        f"Added {request.quantity}x {best_match.name} to inventory"
                    )
                else:
                    response.message = "Failed to update inventory"
            else:
                response.message = (
                    f"Best match: {best_match.name} "
                    f"(confidence: {best_match.confidence:.1%})"
                )
        else:
            response.message = "No card matches found"

        return response

    except Exception as e:
        logger.exception("Quick add failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Quick add failed: {str(e)}",
        )


@router.websocket("/stream")
async def websocket_scanner(websocket: WebSocket):
    """
    WebSocket endpoint for real-time card scanning.

    Protocol:
    - Client sends base64-encoded frames
    - Server responds with scan results

    Message format (client -> server):
    {
        "type": "scan",
        "image": "base64...",
        "detect_only": false
    }

    Message format (server -> client):
    {
        "type": "result",
        "success": true,
        "result": {...}
    }
    """
    await websocket.accept()

    scanner = get_scanner_service()
    if not scanner.is_ready:
        await scanner.initialize()

    try:
        while True:
            # Receive frame
            data = await websocket.receive_json()

            if data.get("type") == "scan":
                try:
                    # Decode image
                    image_data = data.get("image", "")
                    if "," in image_data:
                        image_data = image_data.split(",")[1]

                    image_bytes = base64.b64decode(image_data)
                    image = Image.open(io.BytesIO(image_bytes))

                    # Scan
                    detect_only = data.get("detect_only", False)
                    result = await scanner.scan_image(image, detect_only=detect_only)

                    await websocket.send_json({
                        "type": "result",
                        "success": True,
                        "result": result.to_dict(),
                    })

                except Exception as e:
                    await websocket.send_json({
                        "type": "result",
                        "success": False,
                        "error": str(e),
                    })

            elif data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

            # Small delay to prevent overwhelming the server
            await asyncio.sleep(0.05)

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.exception("WebSocket error")
        try:
            await websocket.close(code=1011, reason=str(e))
        except Exception:
            pass


@router.get("/database/stats")
async def get_database_stats():
    """
    Get statistics about the hash database.

    Returns counts of cards with hashes loaded from Odoo.
    """
    scanner = get_scanner_service()

    if not scanner.matcher._initialized:
        await scanner.matcher.initialize()

    # Check if we have hashes loaded
    if not scanner.matcher._hash_cache:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No hashes loaded from Odoo",
        )

    # Count by set from cache
    set_counts: dict[str, int] = {}
    for _, (_, _, set_name, _, _, _) in scanner.matcher._hash_cache.items():
        set_counts[set_name] = set_counts.get(set_name, 0) + 1

    # Sort by count descending
    top_sets = sorted(
        [{"name": name, "cards": count} for name, count in set_counts.items()],
        key=lambda x: x["cards"],
        reverse=True,
    )[:10]

    return {
        "total_cards": len(scanner.matcher._hash_cache),
        "total_sets": len(set_counts),
        "top_sets": top_sets,
        "source": "Odoo x_phash field",
    }


class TuneRequest(BaseModel):
    """Request to tune scanner parameters."""
    max_distance: int = Field(
        ...,
        ge=10,
        le=200,
        description="Max hash distance threshold (10-200). Lower = stricter matching."
    )


class TuneResponse(BaseModel):
    """Response from tuning operation."""
    success: bool
    max_distance: int
    message: str


@router.get("/settings")
async def get_scanner_settings():
    """
    Get current scanner settings.

    Returns the current configuration values for tuning.
    """
    scanner = get_scanner_service()

    return {
        "max_distance": scanner.matcher.max_distance,
        "hash_count": len(scanner.matcher._hash_cache),
        "detector_conf_threshold": scanner.detector.conf_threshold,
        "recommendations": {
            "strict": {"max_distance": 40, "description": "Very accurate, may miss some cards"},
            "balanced": {"max_distance": 60, "description": "Good balance of accuracy and recall"},
            "loose": {"max_distance": 80, "description": "Finds more cards but less accurate"},
        }
    }


@router.post("/tune", response_model=TuneResponse)
async def tune_scanner(
    request: TuneRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Tune scanner matching threshold.

    Adjusts how strict the hash matching is:
    - Lower values (40-50): Stricter matching, more accurate but may miss cards
    - Medium values (60-70): Balanced matching
    - Higher values (80-100): Looser matching, finds more but less accurate

    This change is temporary and resets on server restart.
    """
    scanner = get_scanner_service()
    scanner.set_max_distance(request.max_distance)

    return TuneResponse(
        success=True,
        max_distance=scanner.matcher.max_distance,
        message=f"Scanner threshold set to {scanner.matcher.max_distance}",
    )


@router.post("/refresh-cache")
async def refresh_hash_cache(
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Force refresh the hash cache from Odoo.

    Use this after running the populate_phash.py script to load new hashes.
    """
    scanner = get_scanner_service()
    await scanner.matcher.refresh_cache()

    return {
        "success": True,
        "hash_count": len(scanner.matcher._hash_cache),
        "message": f"Reloaded {len(scanner.matcher._hash_cache)} hashes from Odoo",
    }
