"""Label generation and printing endpoints."""

import base64
import io
import re

import qrcode
from fastapi import APIRouter, Depends, HTTPException
from PIL import Image
from reportlab.graphics.barcode import code128
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from ..models import LabelRequest, LabelResponse
from ..services import OdooService, get_odoo_service, get_printer_service

router = APIRouter(prefix="/labels", tags=["Labels"])


def extract_variant(name: str) -> tuple[str, str | None]:
    """Extract variant info from card name. Returns (clean_name, variant)."""
    variant_patterns = [
        (r"\s*\((Reverse Holo)\)", r"\1"),
        (r"\s*\((Holo)\)", r"\1"),
        (r"\s*\((Full Art)\)", r"\1"),
        (r"\s*\((Secret)\)", r"\1"),
        (r"\s*\((Promo)\)", r"\1"),
        (r"\s*-\s*(Reverse Holo)", r"\1"),
        (r"\s*-\s*(Holo)", r"\1"),
    ]

    variant = None
    cleaned = name

    for pattern, _ in variant_patterns:
        match = re.search(pattern, name, flags=re.IGNORECASE)
        if match:
            variant = match.group(1)
            cleaned = re.sub(pattern, "", name, flags=re.IGNORECASE).strip()
            break

    return cleaned, variant


def generate_qr_code(data: str, box_size: int = 3) -> Image.Image:
    """Generate a QR code image."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=box_size,
        border=1,
    )
    qr.add_data(data)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white")


def generate_label_pdf(
    sku: str,
    name: str,
    set_name: str | None = None,
    barcode: str | None = None,
) -> bytes:
    """Generate a label PDF for a card with QR code and barcode.

    Label size: 28mm (1.1") wide x 60mm tall - rotated 90° for continuous roll
    Content is rotated so when printed on 1.1" roll, you read it by rotating label.
    """
    # Physical label: 28mm wide x 60mm tall (fits 1.1" continuous roll)
    width = 28 * mm
    height = 60 * mm

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(width, height))

    # White background
    c.setFillColorRGB(1, 1, 1)
    c.rect(0, 0, width, height, fill=1, stroke=0)

    # Rotate canvas 90° - content will read left-to-right when label is turned
    c.saveState()
    c.translate(width, 0)
    c.rotate(90)

    # Now working in rotated space: height becomes "width", width becomes "height"
    # Effective drawing area: 60mm wide x 28mm tall
    draw_width = height  # 60mm
    draw_height = width  # 28mm

    # Extract variant from name
    clean_name, variant = extract_variant(name)

    margin = 2 * mm

    # QR Code - small, top right
    qr_size = 10 * mm
    qr_x = draw_width - qr_size - margin
    qr_y = draw_height - qr_size - margin

    try:
        qr_img = generate_qr_code(sku, box_size=2)
        qr_buffer = io.BytesIO()
        qr_img.save(qr_buffer, format="PNG")
        qr_buffer.seek(0)

        from reportlab.lib.utils import ImageReader

        qr_reader = ImageReader(qr_buffer)
        c.drawImage(qr_reader, qr_x, qr_y, width=qr_size, height=qr_size)
    except Exception:
        c.setStrokeColorRGB(0.5, 0.5, 0.5)
        c.rect(qr_x, qr_y, qr_size, qr_size, fill=0, stroke=1)

    # Left side content
    c.setFillColorRGB(0, 0, 0)

    # Card name at top
    c.setFont("Helvetica-Bold", 6)
    display_name = clean_name[:30] + "..." if len(clean_name) > 30 else clean_name
    c.drawString(margin, draw_height - 5 * mm, display_name)

    # Set name + variant on same line
    c.setFont("Helvetica", 4.5)
    set_display = ""
    if set_name:
        set_display = set_name.replace("Pokemon / ", "").replace("Pokemon/", "")
        set_display = set_display[:22] + "..." if len(set_display) > 22 else set_display
    if variant:
        set_display += f" • {variant}" if set_display else variant
    if set_display:
        c.drawString(margin, draw_height - 8.5 * mm, set_display)

    # Barcode in middle-bottom
    barcode_to_use = barcode or sku
    try:
        barcode_obj = code128.Code128(
            barcode_to_use,
            barWidth=0.2 * mm,
            barHeight=5 * mm,
            humanReadable=False,
        )
        barcode_obj.drawOn(c, margin, 5 * mm)
    except Exception:
        c.setFont("Courier", 4)
        c.drawString(margin, 6 * mm, barcode_to_use[:20])

    # SKU at very bottom
    c.setFont("Courier-Bold", 5)
    c.drawString(margin, 1.5 * mm, sku)

    c.restoreState()
    c.save()
    return buffer.getvalue()


@router.post("/generate", response_model=LabelResponse)
async def generate_label(
    request: LabelRequest,
    odoo: OdooService = Depends(get_odoo_service),
) -> LabelResponse:
    """Generate a label PDF for a product."""
    # Get product details
    records = await odoo.read(
        "product.product",
        [request.product_id],
        ["default_code", "name", "list_price", "barcode", "categ_id"],
    )

    if not records:
        raise HTTPException(
            status_code=404,
            detail=f"Product with ID {request.product_id} not found",
        )

    product = records[0]

    # Handle Odoo False values
    barcode = product.get("barcode")
    if barcode is False:
        barcode = None

    # Get set name from category
    categ = product.get("categ_id")
    set_name = categ[1] if categ and isinstance(categ, (list, tuple)) else None

    try:
        pdf_bytes = generate_label_pdf(
            sku=product.get("default_code") or "N/A",
            name=product.get("name") or "Unknown",
            set_name=set_name,
            barcode=barcode,
        )

        return LabelResponse(
            success=True,
            message=f"Label generated for {product.get('name')}",
            pdf_base64=base64.b64encode(pdf_bytes).decode(),
        )
    except Exception as e:
        return LabelResponse(
            success=False,
            message=f"Failed to generate label: {str(e)}",
            pdf_base64=None,
        )


@router.get("/preview/{product_id}")
async def preview_label(
    product_id: int,
    odoo: OdooService = Depends(get_odoo_service),
) -> LabelResponse:
    """Preview a label without printing."""
    # Reuse generate endpoint logic
    request = LabelRequest(product_id=product_id, quantity=1)
    return await generate_label(request, odoo)


@router.get("/printer/status")
async def printer_status():
    """Get label printer connection status."""
    printer = get_printer_service()
    return printer.get_status()


@router.get("/printer/preview/{product_id}")
async def preview_printer_label(
    product_id: int,
    odoo: OdooService = Depends(get_odoo_service),
):
    """Preview the printer label as PNG image - no paper wasted!"""
    from fastapi.responses import Response

    printer = get_printer_service()

    # Get product details
    records = await odoo.read(
        "product.product",
        [product_id],
        ["default_code", "name", "list_price", "categ_id"],
    )

    if not records:
        raise HTTPException(
            status_code=404,
            detail=f"Product with ID {product_id} not found",
        )

    product = records[0]

    # Extract set name from category
    categ = product.get("categ_id")
    set_name = categ[1] if categ and isinstance(categ, (list, tuple)) else None

    # Extract variant from name
    clean_name, variant = extract_variant(product.get("name") or "Unknown")

    # Generate the label image (same as what would be printed)
    label_image = printer.create_label_image(
        sku=product.get("default_code") or "N/A",
        name=clean_name,
        price=float(product.get("list_price") or 0),
        set_name=set_name,
        variant=variant,
    )

    # Convert to PNG bytes
    img_buffer = io.BytesIO()
    label_image.save(img_buffer, format="PNG")
    img_buffer.seek(0)

    return Response(
        content=img_buffer.getvalue(), media_type="image/png", headers={"Cache-Control": "no-cache"}
    )


@router.post("/print/{product_id}")
async def print_label_direct(
    product_id: int,
    odoo: OdooService = Depends(get_odoo_service),
):
    """Print label directly to Brother QL printer."""
    printer = get_printer_service()

    if not printer.is_available:
        return {
            "success": False,
            "error": "Printer not configured or disabled",
        }

    # Get product details
    records = await odoo.read(
        "product.product",
        [product_id],
        ["default_code", "name", "list_price", "categ_id"],
    )

    if not records:
        raise HTTPException(
            status_code=404,
            detail=f"Product with ID {product_id} not found",
        )

    product = records[0]

    # Extract set name from category
    categ = product.get("categ_id")
    set_name = categ[1] if categ and isinstance(categ, (list, tuple)) else None

    # Extract variant from name
    clean_name, variant = extract_variant(product.get("name") or "Unknown")

    success, message = printer.print_label(
        sku=product.get("default_code") or "N/A",
        name=clean_name,
        price=float(product.get("list_price") or 0),
        set_name=set_name,
        variant=variant,
    )

    if success:
        return {"success": True, "message": message}
    else:
        return {"success": False, "error": message}
