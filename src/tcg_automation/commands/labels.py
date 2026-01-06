"""
Label generation for TCG cards.
"""

import io
import re
import urllib.parse

import qrcode
from PIL import Image
from reportlab.graphics.barcode import code128
from reportlab.lib.units import inch, mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


def parse_sku(sku: str) -> dict:
    """Parse SKU into components."""
    parts = sku.lower().split("-")
    set_code = parts[0].upper() if parts else ""
    card_number = parts[1] if len(parts) > 1 else ""

    variant = "Normal"
    if len(parts) > 2:
        if parts[2] == "holo":
            variant = "Holo"
        elif parts[2] == "reverse":
            variant = "Reverse"

    return {"set_code": set_code, "card_number": card_number, "variant": variant}


def clean_card_name(name: str) -> str:
    """Clean card name to show just name and number."""
    # Remove ALL non-printable ASCII
    clean = re.sub(r'[^a-zA-Z0-9\s\(\)\-\']', '', name)
    # Find pattern like (001), (025), (123) and stop there
    match = re.search(r'^(.+?\(\d{2,3}\))', clean)
    if match:
        return match.group(1).strip()
    return clean.strip()[:25]


def generate_qr_code(data: str, size: int = 100) -> Image.Image:
    """Generate QR code as PIL Image."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=1
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    return img.get_image().resize((size, size))


def generate_label(product: dict) -> bytes:
    """Generate a thin strip label for toploader edge."""
    width = 1.0 * inch
    height = 0.5 * inch

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(width, height))

    sku = product.get("default_code", "")
    name = product.get("name", "Unknown")
    sku_info = parse_sku(sku)

    # Clean and trim name
    display_name = clean_card_name(name)
    if len(display_name) > 20:
        display_name = display_name[:17] + "..."

    padding = 0.5 * mm
    qr_size = 4 * mm

    # QR Code (top-right corner)
    qr_x = width - qr_size - padding
    qr_y = height - qr_size - padding

    qr_url = f"https://www.ebay.com/sch/i.html?_nkw={urllib.parse.quote(name)}"
    qr_img = generate_qr_code(qr_url, size=int(qr_size * 4))

    qr_buffer = io.BytesIO()
    qr_img.save(qr_buffer, format='PNG')
    qr_buffer.seek(0)

    c.drawImage(ImageReader(qr_buffer), qr_x, qr_y, width=qr_size, height=qr_size)

    # Text area (left side)
    text_x = padding

    # Card name
    c.setFont("Helvetica-Bold", 3)
    text_y = height - padding - 2.5
    c.drawString(text_x, text_y, display_name)

    # Set name and variant
    c.setFont("Helvetica", 2)
    text_y -= 3
    c.drawString(text_x, text_y, f"{sku_info['set_code']} | {sku_info['variant']}")

    # Barcode
    barcode_y = padding + 2 * mm
    try:
        barcode = code128.Code128(sku, barHeight=2 * mm, barWidth=0.2, lquiet=0, rquiet=0)
        barcode.drawOn(c, padding, barcode_y)
    except Exception:
        c.setFont("Helvetica", 2)
        c.drawString(text_x, barcode_y, sku)

    # SKU text at bottom
    c.setFont("Helvetica", 2)
    c.drawString(text_x, padding, sku)

    c.save()
    buffer.seek(0)
    return buffer.getvalue()


def generate_labels_pdf(products: list[dict], output_path: str = "labels.pdf") -> str:
    """Generate a PDF with multiple labels."""
    from reportlab.lib.pagesizes import LETTER

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=LETTER)

    label_width = 1.0 * inch
    label_height = 0.5 * inch
    margin = 0.5 * inch
    cols = 7
    rows = 18

    page_width, page_height = LETTER

    for i, product in enumerate(products):
        col = i % cols
        row = (i // cols) % rows

        if i > 0 and i % (cols * rows) == 0:
            c.showPage()

        x = margin + col * label_width
        y = page_height - margin - (row + 1) * label_height

        # Generate individual label as sub-canvas
        label_bytes = generate_label(product)
        # For simplicity, we'll draw directly
        sku = product.get("default_code", "")
        name = product.get("name", "Unknown")
        sku_info = parse_sku(sku)
        display_name = clean_card_name(name)[:17]

        c.setFont("Helvetica-Bold", 5)
        c.drawString(x + 1*mm, y + label_height - 3*mm, display_name)

        c.setFont("Helvetica", 4)
        c.drawString(x + 1*mm, y + label_height - 6*mm, f"{sku_info['set_code']} | {sku_info['variant']}")

        c.setFont("Helvetica", 4)
        c.drawString(x + 1*mm, y + 1*mm, sku)

    c.save()
    buffer.seek(0)

    with open(output_path, "wb") as f:
        f.write(buffer.getvalue())

    return output_path


