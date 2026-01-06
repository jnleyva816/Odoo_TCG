"""Web assets for TCG Automation."""

from pathlib import Path

# Load scanner HTML content
SCANNER_HTML_PATH = Path(__file__).parent / "scanner.html"
SCANNER_HTML = SCANNER_HTML_PATH.read_text(encoding="utf-8") if SCANNER_HTML_PATH.exists() else ""


