"""
Web server for live card scanning.
"""

import io
import logging

from flask import Flask, jsonify, request, send_file, send_from_directory
from flask_cors import CORS

from ..config import get_config
from ..odoo_client import get_odoo_client
from .labels import generate_label, parse_sku

logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """Create and configure Flask application."""
    app = Flask(__name__)
    CORS(app)

    odoo = get_odoo_client()

    @app.route("/")
    def index():
        """Serve the scanner page."""
        try:
            from ..web import SCANNER_HTML
            if SCANNER_HTML:
                return SCANNER_HTML
        except ImportError:
            pass

        return """
        <!DOCTYPE html>
        <html>
        <head><title>TCG Scanner</title></head>
        <body>
            <h1>TCG Card Scanner</h1>
            <p>Scanner UI not found. Check installation.</p>
        </body>
        </html>
        """

    @app.route("/api/status")
    def status():
        """Check server and Odoo status."""
        connected = odoo.connect()
        return jsonify({
            "server": "running",
            "odoo": "connected" if connected else "disconnected"
        })

    @app.route("/api/search")
    def search_products():
        """Search products by name, SKU, or card number."""
        if not odoo.connect():
            return jsonify({"error": "Failed to connect to Odoo"}), 500

        query = request.args.get("q", "").strip()
        set_filter = request.args.get("set", "").strip()
        limit = int(request.args.get("limit", 20))

        if len(query) < 1:
            return jsonify({"results": []})

        # Build search domain
        domain = ["|", "|",
            ("name", "ilike", query),
            ("default_code", "ilike", query),
            ("default_code", "ilike", f"-{query}")
        ]

        if set_filter:
            domain = ["&", ("default_code", "like", f"{set_filter}-")] + domain

        products = odoo.search_read(
            "product.product",
            domain,
            ["id", "name", "default_code", "qty_available", "list_price"],
        )

        # Sort by relevance
        def sort_key(p):
            sku = p.get("default_code", "").lower()
            name = p.get("name", "").lower()
            q = query.lower()

            if sku == q:
                return (0, sku)
            if sku.startswith(q):
                return (1, sku)
            if q in sku:
                return (2, sku)
            if name.startswith(q):
                return (3, name)
            return (4, name)

        products.sort(key=sort_key)
        products = products[:limit]

        results = []
        for p in products:
            sku = p.get("default_code", "")
            sku_info = parse_sku(sku)

            results.append({
                "id": p["id"],
                "sku": sku,
                "name": p["name"],
                "set": sku_info["set_code"],
                "variant": sku_info["variant"],
                "quantity": p["qty_available"],
                "price": p["list_price"],
            })

        return jsonify({"results": results})

    @app.route("/api/add-card", methods=["POST"])
    def add_card():
        """Add a card to inventory."""
        if not odoo.connect():
            return jsonify({"error": "Failed to connect to Odoo"}), 500

        data = request.json
        sku = data.get("sku", "").strip()

        if not sku:
            return jsonify({"error": "SKU required"}), 400

        product = odoo.get_product_by_sku(sku)
        if not product:
            return jsonify({"error": f"Product not found: {sku}"}), 404

        if not odoo.add_stock(product["id"], 1):
            return jsonify({"error": "Failed to add stock"}), 500

        updated = odoo.get_product_by_sku(sku)
        new_qty = updated["qty_available"] if updated else 0

        return jsonify({
            "success": True,
            "sku": sku,
            "name": product["name"],
            "quantity": new_qty,
            "message": f"Added {sku} to inventory (Qty: {new_qty})"
        })

    @app.route("/api/print-label", methods=["GET", "POST"])
    def print_label():
        """Generate and return a label PDF."""
        if not odoo.connect():
            return jsonify({"error": "Failed to connect to Odoo"}), 500

        if request.method == "GET":
            sku = request.args.get("sku", "").strip()
        else:
            data = request.json or {}
            sku = data.get("sku", "").strip()

        if not sku:
            return jsonify({"error": "SKU required"}), 400

        product = odoo.get_product_by_sku(sku)
        if not product:
            return jsonify({"error": f"Product not found: {sku}"}), 404

        pdf_bytes = generate_label(product)

        response = send_file(
            io.BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=False,
            download_name=f"label_{sku}.pdf"
        )

        # Prevent caching
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

        return response

    @app.route("/api/product/<sku>")
    def get_product(sku):
        """Get product info by SKU."""
        if not odoo.connect():
            return jsonify({"error": "Failed to connect to Odoo"}), 500

        product = odoo.get_product_by_sku(sku)
        if not product:
            return jsonify({"error": f"Product not found: {sku}"}), 404

        return jsonify({
            "sku": product["default_code"],
            "name": product["name"],
            "quantity": product["qty_available"],
            "price": product["list_price"],
        })

    return app


def run_server(host: str = "0.0.0.0", port: int = 5000, debug: bool = True):
    """Run the Flask development server."""
    config = get_config()
    app = create_app()

    print("=" * 50)
    print("TCG Card Scanner Server")
    print("=" * 50)
    print(f"Odoo: {config.odoo.url}")
    print(f"Database: {config.odoo.db}")
    print("=" * 50)
    print(f"Open http://localhost:{port} in your browser")
    print("=" * 50)

    app.run(host=host, port=port, debug=debug)

