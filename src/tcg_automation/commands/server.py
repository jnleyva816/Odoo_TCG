"""
Web server for live card scanning.
"""

import base64
import io
import logging
import threading
import time

from flask import Flask, Response, jsonify, request, send_file
from flask_cors import CORS

from ..config import get_config
from ..odoo_client import OdooClient
from .labels import generate_label, parse_sku
from .printer import get_printer

logger = logging.getLogger(__name__)

# Thread-local storage for Odoo connections
_thread_local = threading.local()

# Simple image cache with TTL
_image_cache = {}
_image_cache_lock = threading.Lock()
IMAGE_CACHE_TTL = 3600  # 1 hour
IMAGE_CACHE_MAX_SIZE = 1000  # Max cached images


def get_thread_odoo():
    """Get thread-local Odoo client."""
    if not hasattr(_thread_local, "odoo") or _thread_local.odoo is None:
        _thread_local.odoo = OdooClient()
    return _thread_local.odoo


def get_cached_image(product_id: int) -> bytes | None:
    """Get image from cache if not expired."""
    with _image_cache_lock:
        if product_id in _image_cache:
            data, timestamp = _image_cache[product_id]
            if time.time() - timestamp < IMAGE_CACHE_TTL:
                return data
            else:
                del _image_cache[product_id]
    return None


def set_cached_image(product_id: int, data: bytes):
    """Store image in cache."""
    with _image_cache_lock:
        # Evict old entries if cache is full
        if len(_image_cache) >= IMAGE_CACHE_MAX_SIZE:
            # Remove oldest 10%
            sorted_items = sorted(_image_cache.items(), key=lambda x: x[1][1])
            for key, _ in sorted_items[: IMAGE_CACHE_MAX_SIZE // 10]:
                del _image_cache[key]
        _image_cache[product_id] = (data, time.time())


# Placeholder image (1x1 transparent PNG)
PLACEHOLDER_IMAGE = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


def create_app() -> Flask:
    """Create and configure Flask application."""
    app = Flask(__name__)
    CORS(app)

    # Main Odoo client (for non-threaded operations)
    OdooClient()

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
        odoo = get_thread_odoo()
        connected = odoo.connect()
        return jsonify({"server": "running", "odoo": "connected" if connected else "disconnected"})

    @app.route("/api/search")
    def search_products():
        """Search products by name, SKU, or card number."""
        odoo = get_thread_odoo()
        if not odoo.connect():
            return jsonify({"error": "Failed to connect to Odoo"}), 500

        query = request.args.get("q", "").strip()
        set_filter = request.args.get("set", "").strip()
        limit = int(request.args.get("limit", 20))

        if len(query) < 1:
            return jsonify({"results": []})

        # Build search domain
        domain = [
            "|",
            "|",
            ("name", "ilike", query),
            ("default_code", "ilike", query),
            ("default_code", "ilike", f"-{query}"),
        ]

        if set_filter:
            domain = ["&", ("default_code", "like", f"{set_filter}-")] + domain

        # Limit search at Odoo level for performance
        products = odoo.search_read(
            "product.product",
            domain,
            ["id", "name", "default_code", "qty_available", "list_price"],
            limit=100,  # Limit initial fetch
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

            results.append(
                {
                    "id": p["id"],
                    "sku": sku,
                    "name": p["name"],
                    "set": sku_info["set_code"],
                    "variant": sku_info["variant"],
                    "quantity": p["qty_available"],
                    "price": p["list_price"],
                }
            )

        return jsonify({"results": results})

    @app.route("/api/add-card", methods=["POST"])
    def add_card():
        """Add a card to inventory."""
        odoo = get_thread_odoo()
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

        return jsonify(
            {
                "success": True,
                "sku": sku,
                "name": product["name"],
                "quantity": new_qty,
                "message": f"Added {sku} to inventory (Qty: {new_qty})",
            }
        )

    @app.route("/api/print-label", methods=["GET", "POST"])
    def print_label():
        """Generate and return a label PDF."""
        odoo = get_thread_odoo()
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
            download_name=f"label_{sku}.pdf",
        )

        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

        return response

    @app.route("/api/printer/status")
    def printer_status():
        """Get label printer status."""
        printer = get_printer()
        return jsonify(printer.get_status())

    @app.route("/api/printer/print", methods=["POST"])
    def printer_print():
        """Print label directly to Brother QL printer."""
        printer = get_printer()

        if not printer.is_available:
            return jsonify({"success": False, "error": "Printer not configured or disabled"}), 503

        odoo = get_thread_odoo()
        if not odoo.connect():
            return jsonify({"success": False, "error": "Failed to connect to Odoo"}), 500

        data = request.json or {}
        sku = data.get("sku", "").strip()

        if not sku:
            return jsonify({"success": False, "error": "SKU required"}), 400

        product = odoo.get_product_by_sku(sku)
        if not product:
            return jsonify({"success": False, "error": f"Product not found: {sku}"}), 404

        success, message = printer.print_label(product)

        if success:
            return jsonify({"success": True, "message": message})
        else:
            return jsonify({"success": False, "error": message}), 500

    @app.route("/api/printer/print-batch", methods=["POST"])
    def printer_print_batch():
        """Print multiple labels to Brother QL printer."""
        printer = get_printer()

        if not printer.is_available:
            return jsonify({"success": False, "error": "Printer not configured or disabled"}), 503

        odoo = get_thread_odoo()
        if not odoo.connect():
            return jsonify({"success": False, "error": "Failed to connect to Odoo"}), 500

        data = request.json or {}
        skus = data.get("skus", [])

        if not skus:
            return jsonify({"success": False, "error": "SKUs required"}), 400

        results = []
        success_count = 0

        for sku in skus:
            product = odoo.get_product_by_sku(sku)
            if not product:
                results.append({"sku": sku, "success": False, "error": "Not found"})
                continue

            success, message = printer.print_label(product)
            results.append(
                {
                    "sku": sku,
                    "success": success,
                    "message": message if success else None,
                    "error": message if not success else None,
                }
            )
            if success:
                success_count += 1

        return jsonify(
            {
                "success": success_count > 0,
                "total": len(skus),
                "printed": success_count,
                "failed": len(skus) - success_count,
                "results": results,
            }
        )

    @app.route("/api/inventory")
    def get_inventory():
        """Get inventory with filtering and sorting."""
        odoo = get_thread_odoo()
        if not odoo.connect():
            return jsonify({"error": "Failed to connect to Odoo"}), 500

        set_filter = request.args.get("set", "").strip()
        stock_filter = request.args.get("stock", "all")
        sort_by = request.args.get("sort", "sku")
        sort_order = request.args.get("order", "asc")
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 50))

        # Build domain
        domain = []
        if set_filter:
            domain.append(("default_code", "like", f"{set_filter}-"))
        if stock_filter == "in_stock":
            domain.append(("qty_available", ">", 0))
        elif stock_filter == "out_of_stock":
            domain.append(("qty_available", "<=", 0))

        # Map sort field to Odoo field
        sort_field_map = {
            "sku": "default_code",
            "name": "name",
            "quantity": "qty_available",
            "price": "list_price",
        }
        odoo_sort_field = sort_field_map.get(sort_by, "default_code")
        odoo_order = f"{odoo_sort_field} {'desc' if sort_order == 'desc' else 'asc'}"

        # Get total count efficiently
        total = len(odoo.search("product.product", domain))

        # Fetch paginated products with Odoo-level sorting
        offset = (page - 1) * per_page
        products = odoo.execute(
            "product.product",
            "search_read",
            domain,
            fields=["id", "name", "default_code", "qty_available", "list_price"],
            limit=per_page,
            offset=offset,
            order=odoo_order,
        )

        # Format results
        results = []
        for p in products:
            sku = p.get("default_code", "")
            sku_info = parse_sku(sku)
            results.append(
                {
                    "id": p["id"],
                    "sku": sku,
                    "name": p["name"],
                    "set": sku_info["set_code"],
                    "variant": sku_info["variant"],
                    "quantity": p["qty_available"],
                    "price": p["list_price"],
                }
            )

        return jsonify(
            {
                "results": results,
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": (total + per_page - 1) // per_page if total > 0 else 1,
            }
        )

    @app.route("/api/sets")
    def get_sets():
        """Get list of available sets."""
        odoo = get_thread_odoo()
        if not odoo.connect():
            return jsonify({"error": "Failed to connect to Odoo"}), 500

        # Get Pokemon categories with product counts in one query
        categories = odoo.search_read(
            "product.category", [("parent_id.name", "=", "Pokemon")], ["name"]
        )

        sets = []
        for cat in categories:
            name = cat["name"]
            if ":" in name:
                code = name.split(":")[0].strip().lower()
            else:
                code = name.lower().replace(" ", "")

            count = len(odoo.search("product.product", [("categ_id", "=", cat["id"])]))
            if count > 0:
                sets.append({"code": code, "name": name, "count": count})

        return jsonify({"sets": sets})

    @app.route("/api/product/<sku>")
    def get_product(sku):
        """Get product info by SKU."""
        odoo = get_thread_odoo()
        if not odoo.connect():
            return jsonify({"error": "Failed to connect to Odoo"}), 500

        product = odoo.get_product_by_sku(sku)
        if not product:
            return jsonify({"error": f"Product not found: {sku}"}), 404

        return jsonify(
            {
                "sku": product["default_code"],
                "name": product["name"],
                "quantity": product["qty_available"],
                "price": product["list_price"],
            }
        )

    @app.route("/api/image/<int:product_id>")
    def get_product_image(product_id):
        """Get product image from Odoo with caching."""
        # Check cache first
        cached = get_cached_image(product_id)
        if cached is not None:
            response = Response(cached, mimetype="image/png")
            response.headers["Cache-Control"] = "public, max-age=3600"
            response.headers["X-Cache"] = "HIT"
            return response

        # Fetch from Odoo
        odoo = get_thread_odoo()
        try:
            if not odoo.connect():
                return Response(PLACEHOLDER_IMAGE, mimetype="image/png")

            products = odoo.read(
                "product.product",
                [product_id],
                ["image_128"],  # Use smaller 128px thumbnail for speed
            )

            if not products or not products[0].get("image_128"):
                return Response(PLACEHOLDER_IMAGE, mimetype="image/png")

            image_data = base64.b64decode(products[0]["image_128"])

            # Cache the image
            set_cached_image(product_id, image_data)

            response = Response(image_data, mimetype="image/png")
            response.headers["Cache-Control"] = "public, max-age=3600"
            response.headers["X-Cache"] = "MISS"
            return response

        except Exception as e:
            logger.error(f"Error fetching image for product {product_id}: {e}")
            return Response(PLACEHOLDER_IMAGE, mimetype="image/png")

    @app.route("/api/images/batch", methods=["POST"])
    def get_batch_images():
        """Get multiple images in one request (returns base64)."""
        odoo = get_thread_odoo()
        if not odoo.connect():
            return jsonify({"error": "Failed to connect to Odoo"}), 500

        data = request.json or {}
        product_ids = data.get("ids", [])[:50]  # Max 50 at once

        if not product_ids:
            return jsonify({"images": {}})

        # Check cache for each
        result = {}
        uncached_ids = []

        for pid in product_ids:
            cached = get_cached_image(pid)
            if cached is not None:
                result[pid] = base64.b64encode(cached).decode("ascii")
            else:
                uncached_ids.append(pid)

        # Fetch uncached from Odoo in one call
        if uncached_ids:
            try:
                products = odoo.read("product.product", uncached_ids, ["image_128"])
                for p in products:
                    pid = p["id"]
                    if p.get("image_128"):
                        image_data = base64.b64decode(p["image_128"])
                        set_cached_image(pid, image_data)
                        result[pid] = p["image_128"]  # Already base64
            except Exception as e:
                logger.error(f"Error batch fetching images: {e}")

        return jsonify({"images": result})

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

    app.run(host=host, port=port, debug=debug, threaded=True)
