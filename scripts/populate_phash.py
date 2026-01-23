#!/usr/bin/env python3
"""
Populate x_phash field for Odoo products with perceptual hashes.

This script:
1. Finds products in Odoo that have images
2. Downloads the image, preprocesses it, and computes the perceptual hash
3. Updates the product with the computed hash

The preprocessing matches what the scanner does for camera images:
- Resize to standard card dimensions (250x350)
- This ensures hashes are comparable between database and scanned images

Usage:
    # Dry run (show what would be updated)
    python populate_phash.py --dry-run

    # Actually update products (only ones missing hash)
    python populate_phash.py

    # Force re-hash ALL products (regenerate all hashes)
    python populate_phash.py --force

    # Limit to specific set
    python populate_phash.py --set "SV10: Destined Rivals"
"""

import argparse
import base64
import io
import logging
import os
import sys
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

try:
    import imagehash
except ImportError:
    print("ERROR: imagehash not installed. Run: pip install imagehash")
    sys.exit(1)

from PIL import Image  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Standard card dimensions for hashing (matches scanner preprocessing)
CARD_WIDTH = 250
CARD_HEIGHT = 350


def get_odoo_client():
    """Get Odoo XML-RPC client."""
    import xmlrpc.client

    url = os.getenv("ODOO_URL", "http://localhost:8069")
    db = os.getenv("ODOO_DB", "odoo")
    user = os.getenv("ODOO_USER", "")
    password = os.getenv("ODOO_PASSWORD", "")

    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, user, password, {})

    if not uid:
        raise Exception("Odoo authentication failed")

    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

    return models, db, uid, password


def preprocess_image(image: Image.Image) -> Image.Image:
    """
    Preprocess image to standard card dimensions.

    This matches the preprocessing in the scanner service for consistency.
    Reference images are already clean card images, so we just resize
    to standard dimensions (no need for edge cropping like camera images).
    """
    if image.mode != "RGB":
        image = image.convert("RGB")

    # Resize to standard card dimensions using high-quality resampling
    image = image.resize((CARD_WIDTH, CARD_HEIGHT), Image.Resampling.LANCZOS)

    return image


def compute_phash(image_data: bytes) -> str:
    """Compute perceptual hash from image bytes with preprocessing."""
    image = Image.open(io.BytesIO(image_data))

    # Preprocess to standard dimensions
    image = preprocess_image(image)

    # Compute 16x16 perceptual hash (256 bits)
    return str(imagehash.phash(image, hash_size=16))


def main():
    parser = argparse.ArgumentParser(description="Populate x_phash for Odoo products")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually update")
    parser.add_argument("--force", action="store_true", help="Re-hash ALL products, not just missing ones")
    parser.add_argument("--set", help="Only process products in this set/category")
    parser.add_argument("--limit", type=int, help="Limit number of products to process")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Pokemon Card Hash Generator")
    logger.info("=" * 60)
    logger.info(f"Preprocessing: Resize to {CARD_WIDTH}x{CARD_HEIGHT}")
    logger.info("Hash algorithm: pHash (16x16 = 256 bits)")
    logger.info("")

    logger.info("Connecting to Odoo...")
    models, db, uid, password = get_odoo_client()
    logger.info("Connected!")

    # Build domain for products with images
    domain = [
        ("image_1920", "!=", False),
    ]

    # Only filter for missing hashes if not forcing
    if not args.force:
        domain.append(("x_phash", "=", False))
        logger.info("Mode: Only products missing x_phash")
    else:
        logger.info("Mode: FORCE - Re-hashing ALL products with images")

    # Filter by set if specified
    if args.set:
        # Find category by name
        cat_ids = models.execute_kw(
            db, uid, password,
            "product.category", "search",
            [[("name", "ilike", args.set)]],
        )
        if cat_ids:
            domain.append(("categ_id", "in", cat_ids))
            logger.info(f"Filtering to category: {args.set}")
        else:
            logger.warning(f"Category not found: {args.set}")

    # Find products
    logger.info("Finding products...")
    product_ids = models.execute_kw(
        db, uid, password,
        "product.product", "search",
        [domain],
        {"limit": args.limit} if args.limit else {},
    )

    logger.info(f"Found {len(product_ids)} products to process")

    if not product_ids:
        logger.info("No products need updating!")
        return

    # Process each product
    updated = 0
    errors = 0

    for i, pid in enumerate(product_ids):
        # Read product with image
        products = models.execute_kw(
            db, uid, password,
            "product.product", "read",
            [pid],
            {"fields": ["id", "name", "default_code", "image_1920"]},
        )

        if not products:
            continue

        product = products[0]
        name = product.get("name", "Unknown")
        sku = product.get("default_code", "")
        image_b64 = product.get("image_1920")

        logger.info(f"[{i+1}/{len(product_ids)}] {sku}: {name}")

        if not image_b64:
            logger.warning(f"  No image data for product {pid}")
            errors += 1
            continue

        try:
            # Decode image and compute hash
            image_data = base64.b64decode(image_b64)
            phash = compute_phash(image_data)

            logger.info(f"  Hash: {phash}")

            if not args.dry_run:
                # Update product
                models.execute_kw(
                    db, uid, password,
                    "product.product", "write",
                    [[pid], {"x_phash": phash}],
                )
                updated += 1
            else:
                logger.info(f"  [DRY RUN] Would update x_phash = {phash}")
                updated += 1

        except Exception as e:
            logger.error(f"  Error: {e}")
            errors += 1

    # Summary
    logger.info("")
    logger.info("=" * 50)
    logger.info("COMPLETE")
    logger.info("=" * 50)
    if args.dry_run:
        logger.info(f"  Would update: {updated}")
    else:
        logger.info(f"  Updated: {updated}")
    logger.info(f"  Errors: {errors}")


if __name__ == "__main__":
    main()
