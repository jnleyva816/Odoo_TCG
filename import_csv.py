#!/usr/bin/env python3
"""
Import card sets from local CSV file into Odoo.
Uses same patterns as import_set.py for consistency.
Includes parallel image downloading for speed.
"""

import csv
import os
import re
import sys
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

# Add the src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dotenv import load_dotenv
from tcg_automation.odoo_client import OdooClient
from tcg_automation.commands.barcodes import generate_ean13, get_next_sequence

load_dotenv()

# ============================================================================
# CONFIGURATION - Edit these for different sets
# ============================================================================
CSV_FILE = "/home/jleyva/Odoo_TCG/src/tcg_automation/csvs/SV08SurgingSparksProductsAndPrices.csv"
SET_CODE = "sv08"  # lowercase for SKU consistency
SET_NAME = "SV08: Surging Sparks"  # Category name format: "CODE: Name"
PARENT_CATEGORY = "Pokemon"  # Parent category in Odoo

# Session for faster HTTP requests (connection pooling)
session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0 TCG-Importer/1.0'})


def generate_sku(set_prefix: str, card_number: str, variant: str) -> str:
    """Generate a standardized SKU."""
    sku = f"{set_prefix.lower()}-{card_number.zfill(3)}"
    if variant == "Holofoil":
        sku += "-holo"
    elif variant == "Reverse Holofoil":
        sku += "-reverse"
    return sku


def generate_display_name(name: str, card_number: str, variant: str) -> str:
    """Generate standardized display name."""
    display_name = f"{name} ({card_number.zfill(3)})"
    if variant and variant != "Normal":
        display_name += f" ({variant})"
    return display_name


def download_image(url: str) -> str | None:
    """Download image and return base64 encoded data."""
    try:
        # Try higher resolution first
        high_res_url = url.replace('_200w.jpg', '_400w.jpg')
        resp = session.get(high_res_url, timeout=5)
        if resp.status_code == 200:
            return base64.b64encode(resp.content).decode('utf-8')
        # Fallback to original
        resp = session.get(url, timeout=5)
        if resp.status_code == 200:
            return base64.b64encode(resp.content).decode('utf-8')
    except Exception:
        pass
    return None


def download_images_parallel(cards: list[dict]) -> dict[str, str]:
    """
    Download all unique images in parallel.
    Returns dict of {card_number: base64_image}
    """
    # Get unique images (one per card number, not per variant)
    unique_images = {}
    for row in cards:
        ext_number = row.get('extNumber', '').strip()
        match = re.search(r"(\d+)", ext_number)
        card_number = match.group(1) if match else ext_number
        image_url = row.get('imageUrl', '').strip()
        
        if card_number and image_url and card_number not in unique_images:
            unique_images[card_number] = image_url
    
    print(f"\nDownloading {len(unique_images)} unique card images in parallel...")
    
    image_cache = {}
    completed = 0
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_card = {
            executor.submit(download_image, url): card_num 
            for card_num, url in unique_images.items()
        }
        
        for future in as_completed(future_to_card):
            card_num = future_to_card[future]
            completed += 1
            
            try:
                result = future.result()
                if result:
                    image_cache[card_num] = result
            except Exception:
                pass
            
            # Progress indicator
            if completed % 20 == 0 or completed == len(unique_images):
                print(f"  Downloaded {completed}/{len(unique_images)} images")
    
    print(f"  Successfully cached {len(image_cache)} images")
    return image_cache


def main():
    print("=" * 60)
    print(f"CSV Import: {SET_NAME} ({SET_CODE.upper()})")
    print("=" * 60)
    
    # Connect to Odoo
    print("\nConnecting to Odoo...")
    client = OdooClient()
    if not client.connect():
        print("ERROR: Failed to connect to Odoo")
        sys.exit(1)
    print("Connected!")
    
    # Get or create category (Pokemon / MEP: Mega Evolution Promos)
    print(f"Setting up category: {PARENT_CATEGORY} / {SET_NAME}...")
    category_id = client.get_or_create_category(SET_NAME, PARENT_CATEGORY)
    print(f"Category ID: {category_id}")
    
    # Read CSV
    print(f"\nReading: {CSV_FILE}")
    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    print(f"Total rows: {len(rows)}")
    
    # Filter to cards only
    cards = []
    for row in rows:
        ext_number = row.get('extNumber', '').strip()
        name = row.get('name', '').strip()
        if not ext_number or 'Code Card' in name:
            continue
        cards.append(row)
    
    print(f"Cards to import: {len(cards)}")
    
    # Get next barcode sequence
    print("\nGetting next barcode sequence...")
    next_barcode_seq = get_next_sequence(client)
    print(f"Starting barcode sequence: {next_barcode_seq}")
    
    # Download all images in parallel FIRST
    image_cache = download_images_parallel(cards)
    
    # Process cards
    created = 0
    updated = 0
    errors = 0
    
    print("\nImporting products to Odoo...")
    print("-" * 60)
    
    for i, row in enumerate(cards):
        name = row.get('name', '').strip()
        ext_number = row.get('extNumber', '').strip()
        variant = row.get('subTypeName', 'Normal').strip()
        
        # Extract card number
        match = re.search(r"(\d+)", ext_number)
        card_number = match.group(1) if match else ext_number
        
        # Get price
        try:
            price = float(row.get('marketPrice') or row.get('midPrice') or 0)
        except (ValueError, TypeError):
            price = 0.0
        
        # Generate consistent SKU and name
        sku = generate_sku(SET_CODE, card_number, variant)
        display_name = generate_display_name(name, card_number, variant)
        
        # Progress
        print(f"[{i+1}/{len(cards)}] {sku}: ${price:.2f}", end=" ")
        
        # Check if exists
        existing = client.search('product.product', [('default_code', '=', sku)])
        
        # Build product values
        vals = {
            'name': display_name,
            'default_code': sku,
            'list_price': price,
            'type': 'product',
            'categ_id': category_id,
            'sale_ok': True,
            'purchase_ok': True,
        }
        
        # Add image from cache (same image for all variants of a card)
        if card_number in image_cache:
            vals['image_1920'] = image_cache[card_number]
        
        try:
            if existing:
                client.write('product.product', existing, vals)
                print("-> Updated")
                updated += 1
            else:
                # Generate EAN-13 barcode for new products
                barcode = generate_ean13(next_barcode_seq)
                vals['barcode'] = barcode
                next_barcode_seq += 1
                
                product_id = client.create('product.product', vals)
                print(f"-> Created (ID: {product_id}, Barcode: {barcode})")
                created += 1
        except Exception as e:
            print(f"-> ERROR: {e}")
            errors += 1
    
    # Summary
    print("\n" + "=" * 60)
    print("IMPORT COMPLETE")
    print("=" * 60)
    print(f"  Created: {created}")
    print(f"  Updated: {updated}")
    print(f"  Errors:  {errors}")
    print(f"  Total:   {created + updated}")


if __name__ == '__main__':
    main()
