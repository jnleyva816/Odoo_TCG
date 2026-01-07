"""Brother QL label printer service."""

import io
import logging
import re
import socket
from typing import Optional
from urllib.parse import quote_plus

import barcode
from barcode.writer import ImageWriter
import qrcode
from PIL import Image, ImageDraw, ImageFont

from ..config import get_settings

logger = logging.getLogger(__name__)


def generate_collectr_url(name: str, card_number: str | None) -> str:
    """Generate a Collectr search URL for a Pokemon card.
    
    Args:
        name: Card name (e.g., "Pikachu")
        card_number: Card number (e.g., "(001)" or "001")
    
    Returns:
        Collectr search URL
    """
    # Build search query: name and number only
    # Remove any parentheses from name
    clean_name = name.replace("(", "").replace(")", "")
    parts = [clean_name]
    
    if card_number:
        # Remove all parentheses and keep as plain number
        num = card_number.replace("(", "").replace(")", "")
        parts.append(num)
    
    search_query = " ".join(parts)
    encoded_query = quote_plus(search_query)
    
    # Collectr search URL
    return f"https://app.getcollectr.com/?query={encoded_query}"


def extract_card_number(text: str) -> tuple[str, str | None]:
    """Extract card number from text. Returns (clean_text, number_in_parens).
    
    Examples:
        "001/98" -> ("", "(001)")
        "Charizard 001/98" -> ("Charizard", "(001)")
    """
    # Match patterns like "001/98", "001/099", "1/98"
    match = re.search(r'(\d{1,3})/\d+', text)
    if match:
        num = match.group(1).zfill(3)  # Pad to 3 digits
        clean = re.sub(r'\s*\d{1,3}/\d+\s*', ' ', text).strip()
        return clean, f"({num})"
    return text, None

# Label dimensions in pixels at 300dpi (width x height)
# For die-cut labels, these are the exact required dimensions
LABEL_DIMENSIONS = {
    "29": (306, 0),        # 29mm continuous - variable height
    "62": (696, 0),        # 62mm continuous - variable height
    "29x90": (306, 991),   # 29mm x 90mm die-cut
    "38x90": (403, 991),   # 38mm x 90mm die-cut  
    "62x29": (696, 271),   # 62mm x 29mm die-cut
    "62x100": (696, 1109), # 62mm x 100mm die-cut
    "17x54": (165, 566),   # 17mm x 54mm die-cut
    "17x87": (165, 956),   # 17mm x 87mm die-cut
    "12": (106, 0),        # 12mm continuous
}


def generate_qr_code(data: str, size: int = 100) -> Image.Image:
    """Generate a QR code image."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=1,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    return img.get_image().resize((size, size))


def generate_ean13_image(ean13_code: str, width: int, height: int) -> Image.Image | None:
    """Generate an EAN-13 barcode image using python-barcode.
    
    Args:
        ean13_code: 13-digit EAN-13 barcode string
        width: Desired width in pixels
        height: Desired height in pixels
    
    Returns:
        PIL Image of the barcode, or None if generation fails
    """
    if not ean13_code or len(ean13_code) != 13 or not ean13_code.isdigit():
        logger.warning(f"Invalid EAN-13 code: {ean13_code}")
        return None
    
    try:
        # Create EAN-13 barcode (pass only first 12 digits, library calculates check digit)
        # But we already have the full 13, so we use EAN13 which accepts full code
        EAN13 = barcode.get_barcode_class('ean13')
        
        # Custom writer options for cleaner output
        writer = ImageWriter()
        
        # Generate barcode - EAN13 expects 12 digits (calculates check digit itself)
        # So we pass first 12 digits
        ean = EAN13(ean13_code[:12], writer=writer)
        
        # Render to buffer
        buffer = io.BytesIO()
        ean.write(buffer, options={
            'module_width': 0.4,      # Width of each bar
            'module_height': 15.0,    # Height of bars in mm
            'quiet_zone': 2.0,        # Whitespace on sides
            'font_size': 10,          # Size of text below
            'text_distance': 3.0,     # Distance from bars to text
            'write_text': False,      # Don't include text (we draw SKU separately)
        })
        buffer.seek(0)
        
        # Load and resize
        barcode_img = Image.open(buffer).convert('RGB')
        
        # Resize to fit our label area while maintaining aspect ratio
        barcode_img = barcode_img.resize((width, height), Image.Resampling.LANCZOS)
        
        return barcode_img
        
    except Exception as e:
        logger.error(f"Failed to generate EAN-13 barcode: {e}")
        return None


class PrinterService:
    """Brother QL series label printer interface."""

    def __init__(self):
        self._settings = get_settings()

    @property
    def is_available(self) -> bool:
        """Check if printer is configured and enabled."""
        return self._settings.printer_enabled and bool(self._settings.printer_ip)

    def check_connection(self) -> bool:
        """Test if printer is reachable on the network."""
        if not self.is_available:
            return False

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((self._settings.printer_ip, self._settings.printer_port))
            sock.close()
            return result == 0
        except Exception as e:
            logger.error(f"Printer connection check failed: {e}")
            return False

    def get_status(self) -> dict:
        """Get printer status."""
        connected = self.check_connection() if self.is_available else False
        return {
            "enabled": self._settings.printer_enabled,
            "ip": self._settings.printer_ip,
            "port": self._settings.printer_port,
            "model": self._settings.printer_model,
            "label_size": self._settings.printer_label_size,
            "connected": connected,
        }

    def _load_font(self, size: int, bold: bool = False, mono: bool = False) -> ImageFont.FreeTypeFont:
        """Load a font with fallback options."""
        # Try multiple font paths
        if mono:
            font_names = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
                "/usr/share/fonts/TTF/DejaVuSansMono-Bold.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
                "/usr/share/fonts/truetype/freefont/FreeMono.ttf",
            ]
        elif bold:
            font_names = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            ]
        else:
            font_names = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/TTF/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
            ]
        
        for font_path in font_names:
            try:
                font = ImageFont.truetype(font_path, size)
                logger.info(f"Loaded font: {font_path} at size {size}")
                return font
            except OSError:
                continue
        
        # Last resort - use default but it won't scale well
        logger.warning(f"Could not load any fonts, using default")
        return ImageFont.load_default()

    def _load_font_italic(self, size: int) -> ImageFont.FreeTypeFont:
        """Load an italic font with fallback options."""
        font_names = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
            "/usr/share/fonts/TTF/DejaVuSans-Oblique.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Oblique.ttf",
            "/usr/share/fonts/TTF/DejaVuSansMono-Oblique.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansOblique.ttf",
        ]
        
        for font_path in font_names:
            try:
                font = ImageFont.truetype(font_path, size)
                logger.info(f"Loaded italic font: {font_path} at size {size}")
                return font
            except OSError:
                continue
        
        # Fallback to regular font if no italic available
        logger.warning(f"Could not load italic font, using regular")
        return self._load_font(size, mono=True)

    def create_label_image(
        self,
        sku: str,
        name: str,
        price: float,
        set_name: str | None = None,
        variant: str | None = None,
        barcode_ean13: str | None = None,
    ) -> Image.Image:
        """Create a label image matching the PDF preview layout.
        
        HORIZONTAL layout, rotated 90° for printing on narrow tape.
        ┌─────────────────────────────────────────────────┬─────────┐
        │ Card Name (001)                                 │   QR    │
        │ SV09: Phantasmal Flames - Holo                  │  Code   │
        │ ▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌ (EAN-13 barcode)          │         │
        │ SKU-001-HOLO                                    │         │
        └─────────────────────────────────────────────────┴─────────┘
        
        Args:
            sku: Product SKU (internal reference)
            name: Card name
            price: Card price (not currently displayed)
            set_name: Set name for display
            variant: Card variant (Holo, Reverse, etc.)
            barcode_ean13: EAN-13 barcode from Odoo (13 digits)
        """
        label_size = self._settings.printer_label_size
        
        # Get dimensions for label type
        if label_size in LABEL_DIMENSIONS:
            final_width, final_height = LABEL_DIMENSIONS[label_size]
            if final_height == 0:  # Continuous label
                final_height = 600
        else:
            final_width, final_height = 306, 991

        # Create in LANDSCAPE (swapped) - will rotate at end
        width = final_height   # 991 for 29x90
        height = final_width   # 306 for 29x90

        logger.info(f"Creating label {width}x{height} (landscape) for: {name}")

        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)

        # Load fonts
        font_name = self._load_font(24, bold=True)   # Card name
        font_set = self._load_font(18)                # Set name
        font_sku = self._load_font(14)                # SKU
        font_sku_italic = self._load_font_italic(14)  # SKU italic

        margin = 15
        padding_top = 15  # Top padding (same as margin)
        padding_bottom = 35  # Bottom padding (extra space)
        
        # === Extract card number first (needed for QR code URL) ===
        clean_name, card_number = extract_card_number(name)
        
        # === QR Code - top right corner, links to eBay search ===
        qr_size = 140
        qr_x = width - qr_size - margin
        qr_y = padding_top  # At the top
        
        # Generate Collectr search URL for QR code (name and number only)
        collectr_url = generate_collectr_url(clean_name or name, card_number)
        logger.info(f"QR code URL: {collectr_url}")
        
        try:
            qr_img = generate_qr_code(collectr_url, size=qr_size)
            image.paste(qr_img, (qr_x, qr_y))
        except Exception as e:
            logger.warning(f"QR code generation failed: {e}")
            draw.rectangle([qr_x, qr_y, qr_x + qr_size, qr_y + qr_size], outline="gray", width=2)

        # Text area width (left of QR code)
        text_width = qr_x - margin - 15

        # === Line 1: Card Name (number) ===
        display_name = clean_name if clean_name else name
        if card_number:
            display_name = f"{display_name} {card_number}"
        
        while draw.textlength(display_name, font=font_name) > text_width and len(display_name) > 5:
            # Truncate name but keep the number
            if card_number and card_number in display_name:
                base = display_name.replace(f" {card_number}", "")
                base = base[:-4] + "..." if len(base) > 4 else base
                display_name = f"{base} {card_number}"
            else:
                display_name = display_name[:-4] + "..."
        
        draw.text((margin, padding_top), display_name, font=font_name, fill="black")

        # === Line 2: Set: Name - Variant ===
        set_display = ""
        if set_name:
            # Extract set code if present (e.g., "SV09" from "Pokemon / SV09: Prismatic...")
            clean_set = set_name.replace("Pokemon / ", "").replace("Pokemon/", "")
            set_display = clean_set
        if variant:
            set_display += f" - {variant}" if set_display else variant
        
        if set_display:
            while draw.textlength(set_display, font=font_set) > text_width and len(set_display) > 5:
                set_display = set_display[:-4] + "..."
            draw.text((margin, padding_top + 30), set_display, font=font_set, fill="#444444")

        # === Barcode + SKU at bottom ===
        barcode_height = 50
        barcode_width = text_width
        # Position barcode near bottom with extra bottom padding
        barcode_y = height - padding_bottom - barcode_height - 20  # Leave room for SKU below
        
        # Use EAN-13 barcode if provided, otherwise fall back to custom pattern
        if barcode_ean13:
            barcode_img = generate_ean13_image(barcode_ean13, barcode_width, barcode_height)
            if barcode_img:
                image.paste(barcode_img, (margin, barcode_y))
                logger.info(f"Added EAN-13 barcode: {barcode_ean13}")
            else:
                # Fallback to custom barcode if EAN-13 generation failed
                self._draw_barcode(draw, sku, margin, barcode_y, barcode_width, barcode_height)
        else:
            # No EAN-13 provided, use custom barcode based on SKU
            self._draw_barcode(draw, sku, margin, barcode_y, barcode_width, barcode_height)

        # === SKU - at very bottom (italicized) ===
        draw.text((margin, height - padding_bottom - 12), sku, font=font_sku_italic, fill="black")

        # Debug border
        draw.rectangle([2, 2, width-3, height-3], outline="#dddddd", width=1)

        # Rotate 90° for printing on narrow tape
        image = image.rotate(90, expand=True)

        return image

    def _draw_barcode(self, draw: ImageDraw.Draw, data: str, x: int, y: int, width: int, height: int):
        """Draw a simple barcode pattern."""
        bar_width = max(2, width // (len(data) * 11 + 35))
        current_x = x

        # Start pattern
        for i, pattern in enumerate([2, 1, 1, 2, 3, 2]):
            color = "black" if i % 2 == 0 else "white"
            draw.rectangle([current_x, y, current_x + pattern * bar_width, y + height], fill=color)
            current_x += pattern * bar_width

        # Data encoding
        for char in data:
            char_val = ord(char) % 10
            for i in range(6):
                bar_size = (char_val + i) % 4 + 1
                color = "black" if i % 2 == 0 else "white"
                draw.rectangle([current_x, y, current_x + bar_size * bar_width, y + height], fill=color)
                current_x += bar_size * bar_width
                if current_x > x + width - 20:
                    break
            if current_x > x + width - 20:
                break

    def print_label(
        self,
        sku: str,
        name: str,
        price: float,
        set_name: str | None = None,
        variant: str | None = None,
        barcode: str | None = None,
    ) -> tuple[bool, str]:
        """Print a label. Returns (success, message).
        
        Args:
            sku: Product SKU
            name: Card name
            price: Card price
            set_name: Set name
            variant: Card variant
            barcode: EAN-13 barcode from Odoo (13 digits)
        """
        if not self.is_available:
            return False, "Printer not configured or disabled"

        if not self.check_connection():
            return False, f"Cannot connect to printer at {self._settings.printer_ip}:{self._settings.printer_port}"

        try:
            from brother_ql.conversion import convert
            from brother_ql.raster import BrotherQLRaster
            from brother_ql.backends.network import BrotherQLBackendNetwork

            # Create label image with EAN-13 barcode
            image = self.create_label_image(sku, name, price, set_name, variant, barcode_ean13=barcode)

            # Initialize raster object
            qlr = BrotherQLRaster(self._settings.printer_model)
            qlr.exception_on_warning = True

            # Convert image to printer instructions
            # rotate="0" because we already rotated the image ourselves
            instructions = convert(
                qlr=qlr,
                images=[image],
                label=self._settings.printer_label_size,
                rotate="0",
                threshold=70.0,
                dither=False,
                compress=False,
                red=False,
                dpi_600=False,
                hq=True,
                cut=True,  # Auto-cut after each label
            )

            # Send to printer
            printer_identifier = f"tcp://{self._settings.printer_ip}:{self._settings.printer_port}"
            backend = BrotherQLBackendNetwork(printer_identifier)
            backend.write(instructions)
            backend.dispose()

            logger.info(f"Printed label for {sku}")
            return True, f"Label printed for {sku}"

        except ImportError as e:
            logger.error(f"brother_ql not installed: {e}")
            return False, "brother_ql library not installed. Run: pip install brother-ql"
        except Exception as e:
            logger.error(f"Print failed: {e}")
            return False, f"Print failed: {str(e)}"


    def print_labels_batch(
        self,
        products: list[dict],
    ) -> tuple[int, int, list[str]]:
        """Print labels for multiple products based on their stock quantity.
        
        Args:
            products: List of product dicts with keys:
                - sku (default_code)
                - name
                - price (list_price)
                - set_name (x_set_name)
                - barcode
                - qty (quantity to print)
        
        Returns:
            Tuple of (printed_count, failed_count, error_messages)
        """
        if not self.is_available:
            return 0, len(products), ["Printer not configured or disabled"]

        if not self.check_connection():
            return 0, len(products), [f"Cannot connect to printer at {self._settings.printer_ip}:{self._settings.printer_port}"]

        printed = 0
        failed = 0
        errors = []

        for product in products:
            sku = product.get("sku", "")
            name = product.get("name", "")
            price = product.get("price", 0.0)
            set_name = product.get("set_name")
            barcode_val = product.get("barcode")
            qty = int(product.get("qty", 1))

            # Determine variant from SKU
            variant = None
            if "-holo" in sku.lower():
                variant = "Holofoil"
            elif "-reverse" in sku.lower():
                variant = "Reverse Holofoil"

            # Print qty copies
            for i in range(qty):
                success, msg = self.print_label(
                    sku=sku,
                    name=name,
                    price=price,
                    set_name=set_name,
                    variant=variant,
                    barcode=barcode_val,
                )
                if success:
                    printed += 1
                else:
                    failed += 1
                    errors.append(f"{sku} (copy {i+1}): {msg}")

        return printed, failed, errors


# Singleton instance
_printer_service: PrinterService | None = None


def get_printer_service() -> PrinterService:
    """Get the printer service singleton."""
    global _printer_service
    if _printer_service is None:
        _printer_service = PrinterService()
    return _printer_service

