#!/usr/bin/env python3
"""
Fix Missing Images Script for Odoo TCG Inventory.

This script:
1. Finds products without images in Odoo
2. Attempts to download images from TCGPlayer CDN
3. Updates products with the downloaded images

Run with --dry-run first to see what would be fixed.
"""

import argparse
import base64
import csv
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

# Add the src directory to path (go up two levels from scripts/data/)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

from dotenv import load_dotenv
from tcg_automation.odoo_client import OdooClient

load_dotenv()

# Debug mode
DEBUG = os.environ.get("DEBUG", "0") == "1"

def debug(msg: str):
    """Print debug message with timestamp."""
    if DEBUG:
        print(f"[DEBUG {time.strftime('%H:%M:%S')}] {msg}", flush=True)

# Session for faster HTTP requests
session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0 TCG-Importer/1.0'})

# CSV directory (relative to project root)
CSV_DIR = Path(PROJECT_ROOT) / "src" / "tcg_automation" / "csvs"


def download_image(url: str, timeout: int = 15) -> str | None:
    """Download image and return as base64 string."""
    debug(f"Downloading: {url[:60]}...")
    try:
        # Try to get higher resolution image
        # TCGPlayer URLs often have _200w, try _400w first
        high_res_url = url.replace("_200w", "_400w")
        
        debug(f"  Trying high-res: {high_res_url[:60]}...")
        resp = session.get(high_res_url, timeout=timeout)
        debug(f"  Response: {resp.status_code}")
        
        if resp.status_code != 200:
            # Fall back to original URL
            debug(f"  Falling back to original URL...")
            resp = session.get(url, timeout=timeout)
            debug(f"  Response: {resp.status_code}")
        
        if resp.status_code == 200 and len(resp.content) > 1000:  # Sanity check
            debug(f"  Success! {len(resp.content)} bytes")
            return base64.b64encode(resp.content).decode("utf-8")
        else:
            debug(f"  Failed: status={resp.status_code}, size={len(resp.content)}")
    except Exception as e:
        print(f"      ⚠️ Download failed: {e}", flush=True)
        debug(f"  Exception: {e}")
    return None


def load_csv_image_mapping() -> dict[str, str]:
    """
    Load image URLs from all CSVs.
    Returns dict of {sku: image_url}
    """
    mapping = {}
    
    if not CSV_DIR.exists():
        print(f"⚠️ CSV directory not found: {CSV_DIR}")
        return mapping
    
    for csv_file in CSV_DIR.glob("*.csv"):
        # Determine set code from filename
        filename = csv_file.stem
        
        # Extract set code from filename patterns
        # Map filename prefixes to set codes
        set_code = None
        filename_lower = filename.lower()
        
        if filename_lower.startswith("sv10"):
            set_code = "sv10"
        elif filename_lower.startswith("sv08"):
            set_code = "sv08"
        elif filename_lower.startswith("sv09"):
            set_code = "sv09"
        elif filename_lower.startswith("svprismatic") or filename_lower.startswith("svpe"):
            set_code = "svpe"
        elif filename_lower.startswith("meascended") or filename_lower.startswith("meah"):
            set_code = "meah"
        elif filename_lower.startswith("memegaevolutionpromo") or filename_lower.startswith("mep"):
            set_code = "mep"
        elif filename_lower.startswith("me01") or "megaevolution" in filename_lower:
            set_code = "me01"
        elif filename_lower.startswith("me02") or "phantasmal" in filename_lower:
            set_code = "me02"
        
        if not set_code:
            print(f"   Skipping {filename} (can't determine set code)")
            continue
        
        print(f"   Loading {csv_file.name} (set: {set_code})...")
        
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    ext_number = row.get('extNumber', '').strip()
                    image_url = row.get('imageUrl', '').strip()
                    
                    if not ext_number or not image_url:
                        continue
                    
                    # Extract card number
                    match = re.search(r"(\d+)", ext_number)
                    card_number = match.group(1) if match else ext_number
                    
                    # Generate all variant SKUs
                    for variant_suffix in ['', '-holo', '-reverse']:
                        sku = f"{set_code}-{card_number.zfill(3)}{variant_suffix}"
                        mapping[sku] = image_url
                        
        except Exception as e:
            print(f"   ❌ Error reading {csv_file.name}: {e}")
    
    return mapping


def find_products_without_images(client: OdooClient) -> list[dict]:
    """Find Pokemon products that don't have images."""
    print("\n🔍 Finding Pokemon products without images...", flush=True)
    
    # First find the Pokemon parent category
    debug("Looking for Pokemon parent category...")
    pokemon_cats = client.search_read(
        "product.category",
        [("name", "=", "Pokemon")],
        ["id"],
        limit=1,
    )
    debug(f"Found: {pokemon_cats}")
    
    if not pokemon_cats:
        print("   ⚠️ No 'Pokemon' parent category found", flush=True)
        return []
    
    parent_id = pokemon_cats[0]["id"]
    
    # Get all Pokemon set category IDs
    debug("Getting set categories...")
    set_categories = client.search_read(
        "product.category",
        [("parent_id", "=", parent_id)],
        ["id", "name"],
    )
    debug(f"Found {len(set_categories)} sets")
    
    if not set_categories:
        print("   ⚠️ No Pokemon sets found", flush=True)
        return []
    
    # Check each set for products without images
    # NOTE: Can't use domain filter on image_1920 - it doesn't work correctly in Odoo
    products_without_images = []
    
    for cat in set_categories:
        debug(f"Checking set: {cat['name']}...")
        products = client.search_read(
            "product.product",
            [("categ_id", "=", cat["id"])],
            ["id", "name", "default_code", "categ_id", "image_1920"],
        )
        debug(f"  Found {len(products)} products")
        
        # Check in Python if image is actually empty
        no_image = [p for p in products if not p.get("image_1920")]
        debug(f"  {len(no_image)} without images")
        if no_image:
            print(f"   {cat['name']}: {len(no_image)} without images", flush=True)
            products_without_images.extend(no_image)
    
    print(f"   Total: {len(products_without_images)} Pokemon products without images", flush=True)
    return products_without_images


def find_products_in_set(client: OdooClient, set_name: str) -> list[dict]:
    """Find all products in a specific set."""
    print(f"\n🔍 Finding products in {set_name}...")
    
    # Find category ID
    categories = client.search_read(
        "product.category",
        [("name", "ilike", set_name)],
        ["id", "name"],
        limit=1,
    )
    
    if not categories:
        print(f"   ⚠️ Set '{set_name}' not found")
        return []
    
    category_id = categories[0]["id"]
    
    products = client.search_read(
        "product.product",
        [("categ_id", "=", category_id), ("image_1920", "=", False)],
        ["id", "name", "default_code"],
    )
    
    print(f"   Found {len(products)} products without images in {set_name}")
    return products


def fix_images(
    client: OdooClient,
    products: list[dict],
    image_mapping: dict[str, str],
    dry_run: bool = True,
) -> tuple[int, int]:
    """
    Download and update images for products.
    Returns (fixed, failed) counts.
    """
    fixed = 0
    failed = 0
    
    # Filter to products we have image URLs for
    to_fix = []
    for p in products:
        sku = p.get("default_code", "")
        if sku and sku in image_mapping:
            to_fix.append((p, image_mapping[sku]))
    
    if not to_fix:
        print("   No products to fix (no matching image URLs found)")
        return 0, 0
    
    print(f"\n📥 {'Would download' if dry_run else 'Downloading'} images for {len(to_fix)} products...")
    
    if dry_run:
        for p, url in to_fix[:10]:
            print(f"   Would fix: {p.get('default_code')} -> {url[:50]}...")
        if len(to_fix) > 10:
            print(f"   ... and {len(to_fix) - 10} more")
        return len(to_fix), 0
    
    # Download and update in batches
    for i, (product, url) in enumerate(to_fix):
        sku = product.get("default_code", "")
        print(f"   [{i+1}/{len(to_fix)}] {sku}: ", end="", flush=True)
        
        image_b64 = download_image(url)
        
        if image_b64:
            try:
                client.write("product.product", [product["id"]], {"image_1920": image_b64})
                print("✅ Fixed")
                fixed += 1
            except Exception as e:
                print(f"❌ Update failed: {e}")
                failed += 1
        else:
            print("❌ Download failed")
            failed += 1
    
    return fixed, failed


def main():
    global DEBUG
    
    parser = argparse.ArgumentParser(description="Fix missing images in Odoo TCG database")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    parser.add_argument("--set", type=str, help="Only fix images for a specific set (e.g., 'SV10')")
    parser.add_argument("--limit", type=int, help="Limit number of products to fix")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    args = parser.parse_args()
    
    if args.debug:
        DEBUG = True
    
    print("=" * 60, flush=True)
    print("🖼️  Fix Missing Images", flush=True)
    print("=" * 60, flush=True)
    
    if args.dry_run:
        print("🔒 DRY RUN MODE - No changes will be made", flush=True)
    
    if DEBUG:
        print("🐛 DEBUG MODE ENABLED", flush=True)
    
    # Connect to Odoo
    print("\nConnecting to Odoo...", flush=True)
    debug("Creating OdooClient...")
    client = OdooClient()
    debug("Calling connect()...")
    if not client.connect():
        print("❌ Failed to connect to Odoo", flush=True)
        sys.exit(1)
    print("✅ Connected!", flush=True)
    
    # Load image mappings from CSVs
    print("\n📂 Loading image URLs from CSVs...", flush=True)
    debug("Calling load_csv_image_mapping()...")
    image_mapping = load_csv_image_mapping()
    print(f"   Loaded {len(image_mapping)} image URLs", flush=True)
    
    # Find products without images
    if args.set:
        products = find_products_in_set(client, args.set)
    else:
        products = find_products_without_images(client)
    
    if args.limit:
        products = products[:args.limit]
    
    if not products:
        print("\n✅ No products without images found!")
        return
    
    # Fix images
    fixed, failed = fix_images(client, products, image_mapping, dry_run=args.dry_run)
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 SUMMARY")
    print("=" * 60)
    if args.dry_run:
        print(f"   Would fix: {fixed} products")
    else:
        print(f"   ✅ Fixed: {fixed} products")
        print(f"   ❌ Failed: {failed} products")


if __name__ == "__main__":
    main()

