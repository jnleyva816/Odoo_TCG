#!/usr/bin/env python3
"""
Fix Missing Images using TCGDex API.

This uses the same API that the set import uses, which should be more reliable.
"""

import asyncio
import base64
import os
import sys

import httpx

# Add the src directory to path (go up two levels from scripts/data/)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from dotenv import load_dotenv  # noqa: E402
from tcg_automation.odoo_client import OdooClient  # noqa: E402

load_dotenv()

TCGDEX_API = "https://api.tcgdex.net/v2/en"


async def get_tcgdex_image(card_id: str) -> str | None:
    """Fetch card image from TCGDex API."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Get card details
            resp = await client.get(f"{TCGDEX_API}/cards/{card_id}")
            if resp.status_code != 200:
                return None

            card_info = resp.json()
            image_url = card_info.get("image")

            if not image_url:
                return None

            # Download high quality image
            img_resp = await client.get(f"{image_url}/high.png")
            if img_resp.status_code == 200:
                return base64.b64encode(img_resp.content).decode()

        except Exception as e:
            print(f"      Error: {e}")

    return None


def sku_to_tcgdex_id(sku: str) -> str | None:
    """
    Convert SKU to TCGDex card ID.
    Example: sv10-208-holo -> sv10-208
    """
    parts = sku.split("-")
    if len(parts) >= 2:
        set_code = parts[0]
        card_num = parts[1].lstrip("0")  # Remove leading zeros
        return f"{set_code}-{card_num}"
    return None


def find_products_without_images(client: OdooClient, set_filter: str | None = None) -> list[dict]:
    """Find Pokemon products without images."""
    print("\n🔍 Finding Pokemon products without images...", flush=True)

    # Get Pokemon parent category
    pokemon_cats = client.search_read(
        "product.category",
        [("name", "=", "Pokemon")],
        ["id"],
        limit=1,
    )

    if not pokemon_cats:
        print("   No 'Pokemon' category found")
        return []

    parent_id = pokemon_cats[0]["id"]

    # Get set categories
    domain = [("parent_id", "=", parent_id)]
    if set_filter:
        domain.append(("name", "ilike", set_filter))

    set_categories = client.search_read(
        "product.category",
        domain,
        ["id", "name"],
    )

    products_without_images = []

    for cat in set_categories:
        print(f"   Checking {cat['name']}...", flush=True)

        products = client.search_read(
            "product.product",
            [("categ_id", "=", cat["id"])],
            ["id", "name", "default_code", "image_1920"],
        )

        no_image = [p for p in products if not p.get("image_1920")]
        if no_image:
            print(f"      Found {len(no_image)} without images", flush=True)
            products_without_images.extend(no_image)

    return products_without_images


async def fix_single_product(client: OdooClient, product: dict) -> bool:
    """Fix a single product's image."""
    sku = product.get("default_code", "")
    card_id = sku_to_tcgdex_id(sku)

    if not card_id:
        print(f"   Can't convert SKU to TCGDex ID: {sku}")
        return False

    print(f"   Fetching image for {card_id}...", end=" ", flush=True)

    image_b64 = await get_tcgdex_image(card_id)

    if not image_b64:
        print("❌ No image found")
        return False

    try:
        client.write("product.product", [product["id"]], {"image_1920": image_b64})
        print("✅ Fixed!")
        return True
    except Exception as e:
        print(f"❌ Update failed: {e}")
        return False


async def main_async():
    import argparse

    parser = argparse.ArgumentParser(description="Fix missing images using TCGDex API")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--set", type=str, help="Filter to specific set (e.g., 'SV10')")
    parser.add_argument("--limit", type=int, help="Limit number of products")
    args = parser.parse_args()

    print("=" * 60)
    print("🖼️  Fix Missing Images (TCGDex)")
    print("=" * 60)

    if args.dry_run:
        print("🔒 DRY RUN MODE")

    # Connect to Odoo
    print("\nConnecting to Odoo...", flush=True)
    client = OdooClient()
    if not client.connect():
        print("❌ Failed to connect")
        return
    print("✅ Connected!", flush=True)

    # Find products
    products = find_products_without_images(client, args.set)

    if args.limit:
        products = products[: args.limit]

    if not products:
        print("\n✅ No products without images!")
        return

    print(f"\n📋 Found {len(products)} products to fix", flush=True)

    if args.dry_run:
        for p in products[:10]:
            sku = p.get("default_code", "NO SKU")
            card_id = sku_to_tcgdex_id(sku)
            print(f"   Would fix: {sku} -> {card_id}")
        if len(products) > 10:
            print(f"   ... and {len(products) - 10} more")
        return

    # Fix products
    print("\n🔧 Fixing images...", flush=True)
    fixed = 0
    failed = 0

    for i, product in enumerate(products):
        sku = product.get("default_code", "")
        print(f"[{i+1}/{len(products)}] {sku}: ", end="", flush=True)

        if await fix_single_product(client, product):
            fixed += 1
        else:
            failed += 1

    print(f"\n✅ Fixed: {fixed}, ❌ Failed: {failed}")


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
