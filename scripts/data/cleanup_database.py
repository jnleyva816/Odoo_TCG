#!/usr/bin/env python3
"""
Database Cleanup Script for Odoo TCG Inventory.

This script helps identify and clean up:
1. Duplicate products (same SKU)
2. Products without images
3. Empty sets (categories with no products)
4. Sets that weren't fully imported

Run with --dry-run first to see what would be cleaned.
"""

import argparse
import sys
import os
from collections import defaultdict

# Add the src directory to path (go up two levels from scripts/data/)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

from dotenv import load_dotenv
from tcg_automation.odoo_client import OdooClient

load_dotenv()


def find_duplicates(client: OdooClient) -> dict[str, list[dict]]:
    """Find products with duplicate SKUs."""
    print("\n🔍 Searching for duplicate products...")
    
    # Get all products with SKUs
    products = client.search_read(
        "product.product",
        [("default_code", "!=", False)],
        ["id", "name", "default_code", "qty_available", "create_date"],
    )
    
    # Group by SKU
    sku_groups: dict[str, list[dict]] = defaultdict(list)
    for p in products:
        sku = p.get("default_code", "")
        if sku:
            sku_groups[sku].append(p)
    
    # Filter to only duplicates
    duplicates = {sku: prods for sku, prods in sku_groups.items() if len(prods) > 1}
    
    if duplicates:
        print(f"   Found {len(duplicates)} SKUs with duplicates ({sum(len(p) for p in duplicates.values())} total products)")
    else:
        print("   ✅ No duplicate SKUs found")
    
    return duplicates


def find_products_without_images(client: OdooClient) -> list[dict]:
    """Find products that don't have images."""
    print("\n🔍 Searching for products without images...")
    
    # Get products without images (image_1920 is False/empty)
    products = client.search_read(
        "product.product",
        [("image_1920", "=", False)],
        ["id", "name", "default_code", "categ_id"],
    )
    
    if products:
        print(f"   Found {len(products)} products without images")
    else:
        print("   ✅ All products have images")
    
    return products


def find_empty_sets(client: OdooClient) -> list[dict]:
    """Find categories (sets) with no products."""
    print("\n🔍 Searching for empty sets...")
    
    # Get all categories under "Pokemon"
    pokemon_cats = client.search_read(
        "product.category",
        [("name", "=", "Pokemon")],
        ["id"],
    )
    
    if not pokemon_cats:
        print("   ⚠️ No 'Pokemon' parent category found")
        return []
    
    parent_id = pokemon_cats[0]["id"]
    
    # Get all child categories
    categories = client.search_read(
        "product.category",
        [("parent_id", "=", parent_id)],
        ["id", "name"],
    )
    
    empty_sets = []
    for cat in categories:
        # Count products in this category
        product_count = len(client.search("product.product", [("categ_id", "=", cat["id"])]))
        if product_count == 0:
            empty_sets.append(cat)
    
    if empty_sets:
        print(f"   Found {len(empty_sets)} empty sets (categories with no products)")
    else:
        print("   ✅ All sets have products")
    
    return empty_sets


def get_set_stats(client: OdooClient) -> list[dict]:
    """Get statistics for all sets."""
    print("\n📊 Getting set statistics...")
    
    # Get Pokemon parent category
    pokemon_cats = client.search_read(
        "product.category",
        [("name", "=", "Pokemon")],
        ["id"],
    )
    
    if not pokemon_cats:
        print("   ⚠️ No 'Pokemon' parent category found")
        return []
    
    parent_id = pokemon_cats[0]["id"]
    
    # Get all child categories
    categories = client.search_read(
        "product.category",
        [("parent_id", "=", parent_id)],
        ["id", "name"],
    )
    
    stats = []
    for cat in categories:
        # Count products and products with images
        products = client.search_read(
            "product.product",
            [("categ_id", "=", cat["id"])],
            ["id", "image_1920", "qty_available"],
        )
        
        total = len(products)
        with_images = sum(1 for p in products if p.get("image_1920"))
        in_stock = sum(1 for p in products if p.get("qty_available", 0) > 0)
        
        stats.append({
            "id": cat["id"],
            "name": cat["name"],
            "total_products": total,
            "with_images": with_images,
            "without_images": total - with_images,
            "in_stock": in_stock,
        })
    
    # Sort by name
    stats.sort(key=lambda x: x["name"])
    
    return stats


def delete_duplicates(client: OdooClient, duplicates: dict[str, list[dict]], dry_run: bool = True) -> int:
    """Delete duplicate products, keeping the one with stock or the oldest."""
    deleted = 0
    
    for sku, products in duplicates.items():
        # Sort by: has stock (desc), then by create_date (asc - oldest first)
        products.sort(key=lambda p: (-(p.get("qty_available") or 0), p.get("create_date") or ""))
        
        # Keep the first one (has stock or oldest), delete the rest
        to_keep = products[0]
        to_delete = products[1:]
        
        print(f"   {sku}: Keeping ID {to_keep['id']} (qty: {to_keep.get('qty_available', 0)})")
        
        for p in to_delete:
            if dry_run:
                print(f"      Would delete ID {p['id']} (qty: {p.get('qty_available', 0)})")
            else:
                try:
                    client.unlink("product.product", [p["id"]])
                    print(f"      Deleted ID {p['id']}")
                    deleted += 1
                except Exception as e:
                    print(f"      ❌ Failed to delete ID {p['id']}: {e}")
    
    return deleted


def delete_empty_sets(client: OdooClient, empty_sets: list[dict], dry_run: bool = True) -> int:
    """Delete empty category sets."""
    deleted = 0
    
    for cat in empty_sets:
        if dry_run:
            print(f"   Would delete: {cat['name']} (ID: {cat['id']})")
        else:
            try:
                client.unlink("product.category", [cat["id"]])
                print(f"   Deleted: {cat['name']} (ID: {cat['id']})")
                deleted += 1
            except Exception as e:
                print(f"   ❌ Failed to delete {cat['name']}: {e}")
    
    return deleted


def print_summary(duplicates: dict, no_images: list, empty_sets: list, stats: list):
    """Print a summary of issues found."""
    print("\n" + "=" * 60)
    print("📋 SUMMARY")
    print("=" * 60)
    
    print(f"\n🔄 Duplicate SKUs: {len(duplicates)}")
    if duplicates:
        for sku, prods in list(duplicates.items())[:10]:
            print(f"   • {sku}: {len(prods)} copies")
        if len(duplicates) > 10:
            print(f"   ... and {len(duplicates) - 10} more")
    
    print(f"\n🖼️  Products without images: {len(no_images)}")
    if no_images:
        for p in no_images[:10]:
            print(f"   • {p.get('default_code', 'NO SKU')}: {p.get('name', 'Unknown')}")
        if len(no_images) > 10:
            print(f"   ... and {len(no_images) - 10} more")
    
    print(f"\n📁 Empty sets: {len(empty_sets)}")
    if empty_sets:
        for cat in empty_sets:
            print(f"   • {cat['name']}")
    
    print("\n📊 Set Statistics:")
    print("-" * 60)
    print(f"{'Set Name':<35} {'Total':>6} {'Images':>7} {'Stock':>6}")
    print("-" * 60)
    for s in stats:
        img_status = f"{s['with_images']}/{s['total_products']}"
        print(f"{s['name'][:35]:<35} {s['total_products']:>6} {img_status:>7} {s['in_stock']:>6}")
    print("-" * 60)


def main():
    parser = argparse.ArgumentParser(description="Clean up Odoo TCG database")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    parser.add_argument("--fix-duplicates", action="store_true", help="Delete duplicate products")
    parser.add_argument("--delete-empty-sets", action="store_true", help="Delete empty category sets")
    parser.add_argument("--stats-only", action="store_true", help="Only show statistics, don't look for issues")
    args = parser.parse_args()
    
    print("=" * 60)
    print("🧹 Odoo TCG Database Cleanup")
    print("=" * 60)
    
    if args.dry_run:
        print("🔒 DRY RUN MODE - No changes will be made")
    
    # Connect to Odoo
    print("\nConnecting to Odoo...")
    client = OdooClient()
    if not client.connect():
        print("❌ Failed to connect to Odoo")
        sys.exit(1)
    print("✅ Connected!")
    
    # Get stats
    stats = get_set_stats(client)
    
    if args.stats_only:
        print("\n📊 Set Statistics:")
        print("-" * 60)
        print(f"{'Set Name':<35} {'Total':>6} {'Images':>7} {'Stock':>6}")
        print("-" * 60)
        for s in stats:
            img_status = f"{s['with_images']}/{s['total_products']}"
            print(f"{s['name'][:35]:<35} {s['total_products']:>6} {img_status:>7} {s['in_stock']:>6}")
        print("-" * 60)
        total_products = sum(s['total_products'] for s in stats)
        total_with_images = sum(s['with_images'] for s in stats)
        total_in_stock = sum(s['in_stock'] for s in stats)
        print(f"{'TOTAL':<35} {total_products:>6} {total_with_images:>7} {total_in_stock:>6}")
        return
    
    # Find issues
    duplicates = find_duplicates(client)
    no_images = find_products_without_images(client)
    empty_sets = find_empty_sets(client)
    
    # Print summary
    print_summary(duplicates, no_images, empty_sets, stats)
    
    # Perform cleanup actions
    if args.fix_duplicates and duplicates:
        print("\n🔧 Fixing duplicates...")
        deleted = delete_duplicates(client, duplicates, dry_run=args.dry_run)
        if args.dry_run:
            print(f"   Would delete {deleted} duplicate products")
        else:
            print(f"   Deleted {deleted} duplicate products")
    
    if args.delete_empty_sets and empty_sets:
        print("\n🔧 Deleting empty sets...")
        deleted = delete_empty_sets(client, empty_sets, dry_run=args.dry_run)
        if args.dry_run:
            print(f"   Would delete {deleted} empty sets")
        else:
            print(f"   Deleted {deleted} empty sets")
    
    if not any([args.fix_duplicates, args.delete_empty_sets]):
        print("\n💡 To fix issues, run with:")
        print("   --fix-duplicates     Delete duplicate products")
        print("   --delete-empty-sets  Delete empty category sets")
        print("   --dry-run            Preview changes without making them")
        print("\nExample: python cleanup_database.py --dry-run --fix-duplicates --delete-empty-sets")


if __name__ == "__main__":
    main()

