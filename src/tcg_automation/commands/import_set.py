"""
Import card sets from tcgcsv.com into Odoo.
"""

import base64
import csv
import io
import logging
import re
from typing import Any

import requests
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..odoo_client import get_odoo_client

logger = logging.getLogger(__name__)
console = Console()

# TCGPlayer Group IDs for Pokemon sets
SET_MAPPINGS = {
    # Scarlet & Violet Era
    "sv09": {"group_id": 23901, "name": "Journey Together"},
    "me01": {"group_id": 24380, "name": "Mega Evolution"},
    "me02": {"group_id": 23783, "name": "Phantasmal Flames"},
    "sv08": {"group_id": 23779, "name": "Surging Sparks"},
    "sv07": {"group_id": 23654, "name": "Stellar Crown"},
    "sv06": {"group_id": 23580, "name": "Twilight Masquerade"},
    "sv05": {"group_id": 23457, "name": "Temporal Forces"},
    "sv04": {"group_id": 23360, "name": "Paradox Rift"},
    "sv03": {"group_id": 23218, "name": "Obsidian Flames"},
    "sv02": {"group_id": 23104, "name": "Paldea Evolved"},
    "sv01": {"group_id": 22926, "name": "Scarlet & Violet"},
    # Add more sets as needed
}


def generate_sku(set_prefix: str, card_number: str, variant: str) -> str:
    """Generate a standardized SKU."""
    sku = f"{set_prefix.lower()}-{card_number.zfill(3)}"
    if variant == "Holofoil":
        sku += "-holo"
    elif variant == "Reverse Holofoil":
        sku += "-reverse"
    return sku


def fetch_set_data(group_id: int) -> tuple[list[dict], list[dict]]:
    """Fetch product and price data from tcgcsv.com."""
    products_url = f"https://tcgcsv.com/tcgplayer/{group_id}/products"
    prices_url = f"https://tcgcsv.com/tcgplayer/{group_id}/prices"

    console.print(f"[blue]Fetching products from tcgcsv.com (Group {group_id})...[/blue]")
    products_resp = requests.get(products_url, timeout=30)
    products_resp.raise_for_status()

    console.print("[blue]Fetching prices...[/blue]")
    prices_resp = requests.get(prices_url, timeout=30)
    prices_resp.raise_for_status()

    # Parse CSVs
    products = list(csv.DictReader(io.StringIO(products_resp.text)))
    prices = list(csv.DictReader(io.StringIO(prices_resp.text)))

    return products, prices


def download_image(url: str) -> str | None:
    """Download image and convert to base64."""
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return base64.b64encode(resp.content).decode("utf-8")
    except Exception as e:
        logger.warning(f"Failed to download image: {e}")
        return None


def import_set(
    set_code: str,
    dry_run: bool = False,
    delete_existing: bool = False,
    skip_images: bool = False,
) -> dict[str, Any]:
    """
    Import a card set into Odoo.

    Args:
        set_code: Set code (e.g., 'sv09', 'me02')
        dry_run: If True, don't actually create products
        delete_existing: If True, delete existing products first
        skip_images: If True, don't download images

    Returns:
        Summary of import results
    """
    if set_code.lower() not in SET_MAPPINGS:
        available = ", ".join(SET_MAPPINGS.keys())
        console.print(f"[red]Unknown set: {set_code}[/red]")
        console.print(f"[yellow]Available sets: {available}[/yellow]")
        return {"error": f"Unknown set: {set_code}"}

    set_info = SET_MAPPINGS[set_code.lower()]
    group_id = set_info["group_id"]
    set_name = set_info["name"]

    console.print(f"[bold green]Importing: {set_name} ({set_code.upper()})[/bold green]")

    # Fetch data
    products, prices = fetch_set_data(group_id)
    console.print(f"[green]Found {len(products)} products, {len(prices)} price entries[/green]")

    # Build price lookup
    price_lookup: dict[str, float] = {}
    for p in prices:
        if p.get("subTypeName") in ("Normal", "Holofoil", "Reverse Holofoil"):
            product_id = p.get("productId", "")
            variant = p.get("subTypeName", "Normal")
            price = float(p.get("marketPrice") or p.get("midPrice") or 0)
            price_lookup[f"{product_id}:{variant}"] = price

    # Filter to cards only
    cards = [p for p in products if p.get("categoryId") == "3"]
    console.print(f"[green]Filtered to {len(cards)} cards[/green]")

    if dry_run:
        console.print("[yellow]DRY RUN - no changes will be made[/yellow]")

    odoo = get_odoo_client()
    if not odoo.connect():
        return {"error": "Failed to connect to Odoo"}

    # Get or create category
    if not dry_run:
        category_id = odoo.get_or_create_category(set_name)
    else:
        category_id = 0

    # Delete existing if requested
    if delete_existing and not dry_run:
        console.print("[yellow]Deleting existing products...[/yellow]")
        existing = odoo.search("product.product", [("default_code", "like", f"{set_code.lower()}-")])
        if existing:
            odoo.unlink("product.product", existing)
            console.print(f"[yellow]Deleted {len(existing)} existing products[/yellow]")

    # Process cards
    stats = {"created": 0, "skipped": 0, "errors": 0}
    variants = ["Normal", "Holofoil", "Reverse Holofoil"]

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Importing cards...", total=len(cards) * len(variants))

        for card in cards:
            name = card.get("name", "Unknown")
            product_id = card.get("productId", "")
            ext_number = card.get("extNumber", "")
            image_url = card.get("imageUrl", "")

            # Extract card number
            match = re.search(r"(\d+)", ext_number)
            card_number = match.group(1) if match else ext_number

            for variant in variants:
                progress.update(task, advance=1)

                sku = generate_sku(set_code, card_number, variant)
                display_name = f"{name} ({card_number.zfill(3)})"
                if variant != "Normal":
                    display_name += f" ({variant})"

                # Check price
                price_key = f"{product_id}:{variant}"
                price = price_lookup.get(price_key, 0.0)

                # Skip variants with no price (likely don't exist)
                if price == 0 and variant != "Normal":
                    continue

                if dry_run:
                    console.print(f"  [dim]Would create: {display_name} ({sku}) @ ${price:.2f}[/dim]")
                    stats["created"] += 1
                    continue

                # Check if exists
                existing = odoo.get_product_by_sku(sku)
                if existing and not delete_existing:
                    stats["skipped"] += 1
                    continue

                # Download image (only for first variant to save bandwidth)
                image_b64 = None
                if not skip_images and image_url and variant == "Normal":
                    image_b64 = download_image(image_url)

                # Create product
                try:
                    odoo.create("product.product", {
                        "name": display_name,
                        "default_code": sku,
                        "list_price": price,
                        "categ_id": category_id,
                        "type": "product",
                        "image_1920": image_b64,
                        "x_rarity": card.get("rarityName", ""),
                        "x_set_name": set_name,
                    })
                    stats["created"] += 1
                except Exception as e:
                    logger.error(f"Failed to create {sku}: {e}")
                    stats["errors"] += 1

    console.print(f"\n[bold green]Import complete![/bold green]")
    console.print(f"  Created: {stats['created']}")
    console.print(f"  Skipped: {stats['skipped']}")
    console.print(f"  Errors: {stats['errors']}")

    return stats


