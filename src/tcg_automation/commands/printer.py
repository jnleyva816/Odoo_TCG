"""
Brother QL label printer integration.
Supports direct printing to Brother QL-800W network printer.
"""

import logging
import socket

from PIL import Image, ImageDraw, ImageFont

from ..config import get_config
from .labels import clean_card_name, parse_sku

logger = logging.getLogger(__name__)

# Label dimensions for different sizes (width x height in pixels at 300dpi)
# For continuous labels, width is the tape width, height is variable
LABEL_SIZES = {
    "29x90": (991, 306),  # 29mm x 90mm (standard address label)
    "62": (696, 450),  # 62mm continuous (variable height)
    "29": (306, 991),  # 29mm continuous (~1.1" x 3.3" - rotated for length)
    "38x90": (991, 403),  # 38mm x 90mm
    "62x29": (306, 696),  # 62mm x 29mm
    "62x100": (1109, 696),  # 62mm x 100mm
    "17x54": (566, 165),  # 17mm x 54mm
    "17x87": (956, 165),  # 17mm x 87mm
}


class BrotherQLPrinter:
    """Brother QL series label printer interface."""

    def __init__(self):
        self.config = get_config().printer
        self._backend = None

    @property
    def is_available(self) -> bool:
        """Check if printer is configured and enabled."""
        return self.config.validate()

    def check_connection(self) -> bool:
        """Test if printer is reachable on the network."""
        if not self.is_available:
            return False

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((self.config.ip, self.config.port))
            sock.close()
            return result == 0
        except Exception as e:
            logger.error(f"Printer connection check failed: {e}")
            return False

    def get_status(self) -> dict:
        """Get printer status."""
        return {
            "enabled": self.config.enabled,
            "ip": self.config.ip,
            "port": self.config.port,
            "model": self.config.model,
            "label_size": self.config.label_size,
            "connected": self.check_connection() if self.is_available else False,
        }

    def create_label_image(self, product: dict) -> Image.Image:
        """Create a label image for a product."""
        label_size = self.config.label_size

        # Get dimensions for the label
        if label_size in LABEL_SIZES:
            width, height = LABEL_SIZES[label_size]
        else:
            width, height = 306, 991  # Default to 29mm continuous

        # Create image with white background
        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)

        # Get product info
        sku = product.get("default_code", "")
        name = product.get("name", "Unknown")
        price = product.get("list_price", 0)
        sku_info = parse_sku(sku)

        # Clean the card name
        display_name = clean_card_name(name)

        # For narrow labels (29mm), use smaller fonts and vertical layout
        is_narrow = width <= 350

        if is_narrow:
            # Vertical layout for 29mm continuous tape
            # Fonts sized for narrow tape
            try:
                font_large = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24
                )
                font_medium = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18
                )
                font_small = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16
                )
            except OSError:
                try:
                    font_large = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf", 24)
                    font_medium = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans.ttf", 18)
                    font_small = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans.ttf", 16)
                except OSError:
                    font_large = ImageFont.load_default()
                    font_medium = font_large
                    font_small = font_large

            padding = 10
            y_pos = padding

            # Truncate name to fit narrow width
            max_chars = 18
            if len(display_name) > max_chars:
                display_name = display_name[: max_chars - 2] + ".."

            # Price (top, prominent)
            price_text = f"${price:.2f}"
            price_bbox = draw.textbbox((0, 0), price_text, font=font_large)
            price_width = price_bbox[2] - price_bbox[0]
            draw.text(
                ((width - price_width) // 2, y_pos), price_text, font=font_large, fill="black"
            )
            y_pos += 32

            # Divider line
            draw.line([(padding, y_pos), (width - padding, y_pos)], fill="gray", width=1)
            y_pos += 8

            # Card name (bold, centered)
            name_bbox = draw.textbbox((0, 0), display_name, font=font_medium)
            name_width = name_bbox[2] - name_bbox[0]
            draw.text(
                ((width - name_width) // 2, y_pos), display_name, font=font_medium, fill="black"
            )
            y_pos += 26

            # Set code and variant
            set_variant = f"{sku_info['set_code']} {sku_info['variant']}"
            sv_bbox = draw.textbbox((0, 0), set_variant, font=font_small)
            sv_width = sv_bbox[2] - sv_bbox[0]
            draw.text(((width - sv_width) // 2, y_pos), set_variant, font=font_small, fill="gray")
            y_pos += 24

            # SKU
            sku_bbox = draw.textbbox((0, 0), sku, font=font_small)
            sku_width = sku_bbox[2] - sku_bbox[0]
            draw.text(((width - sku_width) // 2, y_pos), sku, font=font_small, fill="black")
            y_pos += 28

            # Barcode at bottom
            barcode_height = 45
            barcode_y = y_pos + 5
            self._draw_barcode(draw, sku, padding, barcode_y, width - 2 * padding, barcode_height)

            # Crop to actual content height + padding
            final_height = barcode_y + barcode_height + padding + 10
            image = image.crop((0, 0, width, min(final_height, height)))

        else:
            # Standard horizontal layout for wider labels
            if len(display_name) > 30:
                display_name = display_name[:27] + "..."

            try:
                font_large = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32
                )
                font_medium = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24
                )
                font_small = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20
                )
            except OSError:
                try:
                    font_large = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf", 32)
                    font_medium = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans.ttf", 24)
                    font_small = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans.ttf", 20)
                except OSError:
                    font_large = ImageFont.load_default()
                    font_medium = font_large
                    font_small = font_large

            padding = 15
            y_pos = padding

            # Card name (top, bold)
            draw.text((padding, y_pos), display_name, font=font_large, fill="black")
            y_pos += 40

            # Set code and variant
            set_variant = f"{sku_info['set_code']} | {sku_info['variant']}"
            draw.text((padding, y_pos), set_variant, font=font_medium, fill="gray")
            y_pos += 30

            # SKU (monospace-style)
            draw.text((padding, y_pos), sku, font=font_medium, fill="black")

            # Price on the right side
            price_text = f"${price:.2f}"
            price_bbox = draw.textbbox((0, 0), price_text, font=font_large)
            price_width = price_bbox[2] - price_bbox[0]
            draw.text(
                (width - padding - price_width, padding), price_text, font=font_large, fill="black"
            )

            # Draw barcode at bottom
            barcode_y = height - 50
            barcode_height = 35
            self._draw_barcode(draw, sku, padding, barcode_y, width - 2 * padding, barcode_height)

        return image

    def _draw_barcode(
        self, draw: ImageDraw.Draw, data: str, x: int, y: int, width: int, height: int
    ):
        """Draw a simple Code 128-style barcode pattern."""
        # Simple barcode visualization using the data characters
        bar_width = max(2, width // (len(data) * 11 + 35))
        current_x = x

        # Start pattern
        for i, pattern in enumerate([2, 1, 1, 2, 3, 2]):
            color = "black" if i % 2 == 0 else "white"
            draw.rectangle([current_x, y, current_x + pattern * bar_width, y + height], fill=color)
            current_x += pattern * bar_width

        # Data encoding (simplified visual representation)
        for char in data:
            char_val = ord(char) % 10
            for i in range(6):
                bar_size = (char_val + i) % 4 + 1
                color = "black" if i % 2 == 0 else "white"
                draw.rectangle(
                    [current_x, y, current_x + bar_size * bar_width, y + height], fill=color
                )
                current_x += bar_size * bar_width
                if current_x > x + width - 20:
                    break
            if current_x > x + width - 20:
                break

        # Stop pattern
        for i, pattern in enumerate([2, 3, 3, 1, 1, 1, 2]):
            if current_x > x + width:
                break
            color = "black" if i % 2 == 0 else "white"
            draw.rectangle([current_x, y, current_x + pattern * bar_width, y + height], fill=color)
            current_x += pattern * bar_width

    def print_label(self, product: dict) -> tuple[bool, str]:
        """
        Print a label for the given product.
        Returns (success, message).
        """
        if not self.is_available:
            return False, "Printer not configured or disabled"

        if not self.check_connection():
            return False, f"Cannot connect to printer at {self.config.ip}:{self.config.port}"

        try:
            # Import brother_ql components
            from brother_ql.backends.network import BrotherQLBackendNetwork
            from brother_ql.conversion import convert
            from brother_ql.raster import BrotherQLRaster

            # Create the label image
            image = self.create_label_image(product)

            # Initialize raster object for the printer model
            qlr = BrotherQLRaster(self.config.model)
            qlr.exception_on_warning = True

            # Determine the label type for brother_ql
            label_type = self._get_brother_ql_label_type()

            # Convert image to printer instructions
            instructions = convert(
                qlr=qlr,
                images=[image],
                label=label_type,
                rotate="auto",
                threshold=70.0,
                dither=False,
                compress=False,
                red=False,
                dpi_600=False,
                hq=True,
                cut=True,
            )

            # Send to printer
            printer_identifier = f"tcp://{self.config.ip}:{self.config.port}"
            backend = BrotherQLBackendNetwork(printer_identifier)
            backend.write(instructions)
            backend.dispose()

            sku = product.get("default_code", "unknown")
            logger.info(f"Printed label for {sku}")
            return True, f"Label printed for {sku}"

        except ImportError as e:
            logger.error(f"brother_ql not installed: {e}")
            return False, "brother_ql library not installed. Run: pip install brother-ql"
        except Exception as e:
            logger.error(f"Print failed: {e}")
            return False, f"Print failed: {str(e)}"

    def _get_brother_ql_label_type(self) -> str:
        """Convert our label size to brother_ql label type."""
        size_map = {
            "29x90": "29x90",
            "62": "62",
            "29": "29",
            "38x90": "38x90",
            "62x29": "62x29",
            "62x100": "62x100",
            "17x54": "17x54",
            "17x87": "17x87",
        }
        return size_map.get(self.config.label_size, "29x90")

    def print_label_from_image(self, image: Image.Image) -> tuple[bool, str]:
        """Print a label from a PIL Image directly."""
        if not self.is_available:
            return False, "Printer not configured or disabled"

        if not self.check_connection():
            return False, f"Cannot connect to printer at {self.config.ip}:{self.config.port}"

        try:
            from brother_ql.backends.network import BrotherQLBackendNetwork
            from brother_ql.conversion import convert
            from brother_ql.raster import BrotherQLRaster

            qlr = BrotherQLRaster(self.config.model)
            qlr.exception_on_warning = True

            label_type = self._get_brother_ql_label_type()

            instructions = convert(
                qlr=qlr,
                images=[image],
                label=label_type,
                rotate="auto",
                threshold=70.0,
                dither=False,
                compress=False,
                red=False,
                dpi_600=False,
                hq=True,
                cut=True,
            )

            printer_identifier = f"tcp://{self.config.ip}:{self.config.port}"
            backend = BrotherQLBackendNetwork(printer_identifier)
            backend.write(instructions)
            backend.dispose()

            return True, "Label printed successfully"

        except ImportError:
            return False, "brother_ql library not installed"
        except Exception as e:
            logger.error(f"Print failed: {e}")
            return False, f"Print failed: {str(e)}"


# Global printer instance
_printer: BrotherQLPrinter | None = None


def get_printer() -> BrotherQLPrinter:
    """Get the global printer instance."""
    global _printer
    if _printer is None:
        _printer = BrotherQLPrinter()
    return _printer
