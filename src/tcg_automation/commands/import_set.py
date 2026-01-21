"""
Import card sets from local CSV files into Odoo.

Reads from organized CSV structure:
    csvs/
      sv09/
        2026-01-16_ProductsAndPrices.csv  ← uses latest
      sv08/
        ...

Features:
- Parallel image downloading for speed
- Higher resolution image attempts
- Update capability for existing products
- Parent category hierarchy (Pokemon / Set Name)
"""

import base64
import csv
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import requests
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

from ..odoo_client import get_odoo_client
from ..price_history import init_price_history_table, record_prices_batch
from .barcodes import generate_ean13, get_next_sequence
from .download import CSV_BASE_DIR, SKU_PREFIXES, get_latest_csv

logger = logging.getLogger(__name__)
console = Console()

# Session for faster HTTP requests (connection pooling)
session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 TCG-Importer/1.0"})

# Parent category for all Pokemon sets in Odoo
PARENT_CATEGORY = "Pokemon"


def generate_sku(set_code: str, card_number: str, variant: str) -> str:
    """Generate a standardized SKU using the SKU prefix mapping."""
    # Use the SKU prefix mapping to get the correct prefix for existing products
    prefix = SKU_PREFIXES.get(set_code.lower(), set_code.lower())
    sku = f"{prefix}-{card_number.zfill(3)}"
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


def load_csv_data(csv_path: Path) -> list[dict]:
    """
    Load and parse a CSV file.

    Returns:
        List of dicts with card data
    """
    with open(csv_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return rows


def download_image(url: str) -> str | None:
    """Download image and return base64 encoded data. Tries higher resolution first."""
    try:
        # Try higher resolution first
        high_res_url = url.replace("_200w.jpg", "_400w.jpg")
        resp = session.get(high_res_url, timeout=10)
        if resp.status_code == 200:
            return base64.b64encode(resp.content).decode("utf-8")
        # Fallback to original
        resp = session.get(url, timeout=10)
        if resp.status_code == 200:
            return base64.b64encode(resp.content).decode("utf-8")
    except Exception as e:
        logger.warning(f"Failed to download image: {e}")
    return None


def download_images_parallel(cards: list[dict]) -> dict[str, str]:
    """
    Download all unique images in parallel.
    Returns dict of {card_number: base64_image}
    """
    # Get unique images (one per card number, not per variant)
    unique_images = {}
    for card in cards:
        ext_number = card.get("extNumber", "").strip()
        match = re.search(r"(\d+)", ext_number)
        card_number = match.group(1) if match else ext_number
        image_url = card.get("imageUrl", "").strip()

        if card_number and image_url and card_number not in unique_images:
            unique_images[card_number] = image_url

    console.print(
        f"[blue]Downloading {len(unique_images)} unique card images in parallel...[/blue]"
    )

    image_cache: dict[str, str] = {}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Downloading images...", total=len(unique_images))

        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_card = {
                executor.submit(download_image, url): card_num
                for card_num, url in unique_images.items()
            }

            for future in as_completed(future_to_card):
                card_num = future_to_card[future]
                progress.update(task, advance=1)

                try:
                    result = future.result()
                    if result:
                        image_cache[card_num] = result
                except Exception:
                    pass

    console.print(
        f"[green]Successfully downloaded {len(image_cache)}/{len(unique_images)} images[/green]"
    )
    return image_cache


def get_available_sets() -> dict[str, dict]:
    """
    Get all available sets that have been downloaded.

    Returns:
        Dict mapping set_code to set info
    """
    available = {}
    if not CSV_BASE_DIR.exists():
        return available

    for set_dir in CSV_BASE_DIR.iterdir():
        if set_dir.is_dir():
            csv_files = list(set_dir.glob("*_ProductsAndPrices.csv"))
            if csv_files:
                available[set_dir.name.lower()] = {
                    "path": set_dir,
                    "csv_count": len(csv_files),
                    "latest": sorted(csv_files, reverse=True)[0],
                }

    return available


def import_set(
    set_code: str,
    dry_run: bool = False,
    delete_existing: bool = False,
    skip_images: bool = False,
) -> dict[str, Any]:
    """
    Import a card set into Odoo from local CSV.

    Args:
        set_code: Set code (e.g., 'sv09', 'me02')
        dry_run: If True, don't actually create products
        delete_existing: If True, delete existing products first
        skip_images: If True, don't download images

    Returns:
        Summary of import results
    """
    console.print(f"[dim]Looking for CSV in: {CSV_BASE_DIR / set_code.lower()}[/dim]")

    # Find the CSV file
    csv_path = get_latest_csv(set_code)
    console.print(f"[dim]Found CSV: {csv_path}[/dim]" if csv_path else "[red]No CSV found![/red]")
    if not csv_path:
        available = get_available_sets()
        if available:
            console.print(f"[red]No CSV found for set: {set_code}[/red]")
            console.print("[yellow]Available sets:[/yellow]")
            for code in sorted(available.keys()):
                console.print(f"  - {code.upper()}")
            console.print("\n[dim]Run 'tcg download {set_code}' first to download the CSV[/dim]")
        else:
            console.print("[red]No CSVs found. Run 'tcg download --all' first.[/red]")
        return {"error": f"No CSV found for set: {set_code}"}

    # Get proper set name from local mapping (no API call needed)
    from .download import SET_NAMES

    set_name = SET_NAMES.get(set_code.lower(), set_code.upper())
    console.print(f"[dim]Set name: {set_name}[/dim]")

    console.print(f"[bold green]Importing: {set_code.upper()}[/bold green]")
    console.print(f"[dim]CSV: {csv_path}[/dim]")

    # Load CSV data
    all_rows = load_csv_data(csv_path)
    console.print(f"[green]Loaded {len(all_rows)} rows from CSV[/green]")

    # Filter to cards only - cards have extNumber field populated
    cards = [
        row
        for row in all_rows
        if row.get("extNumber")
        and row.get("extNumber").strip()
        and "Code Card" not in row.get("name", "")
    ]
    console.print(f"[green]Filtered to {len(cards)} cards (excluding sealed/accessories)[/green]")

    if not cards:
        console.print("[yellow]No cards found in this set[/yellow]")
        return {"error": "No cards found"}

    if dry_run:
        console.print("[yellow]DRY RUN - no changes will be made[/yellow]")
        console.print("\n[bold]Sample cards that would be imported:[/bold]")
        for card in cards[:15]:
            name = card.get("name", "Unknown")
            ext_number = card.get("extNumber", "?")
            rarity = card.get("extRarity", "")
            variant = card.get("subTypeName", "Normal") or "Normal"
            price = card.get("marketPrice") or card.get("midPrice") or "0"
            # Extract just the number (e.g., "001" from "001/159")
            match = re.search(r"(\d+)", ext_number)
            card_number = match.group(1) if match else ext_number
            sku = generate_sku(set_code, card_number, variant)
            display_name = generate_display_name(name, card_number, variant)
            console.print(f"  {sku}: {display_name} - {rarity} - {variant} @ ${price}")
        if len(cards) > 15:
            console.print(f"  ... and {len(cards) - 15} more")
        return {"created": len(cards), "dry_run": True}

    console.print("[dim]Connecting to Odoo...[/dim]")
    odoo = get_odoo_client()
    if not odoo.connect():
        return {"error": "Failed to connect to Odoo"}
    console.print("[green]✓ Connected to Odoo[/green]")

    # Get or create category with parent hierarchy (Pokemon / Set Name)
    console.print(f"[dim]Getting/creating category: {PARENT_CATEGORY} / {set_name}[/dim]")
    category_id = odoo.get_or_create_category(set_name, PARENT_CATEGORY)
    console.print(f"[blue]Category: {PARENT_CATEGORY} / {set_name} (ID: {category_id})[/blue]")

    # Delete existing if requested
    if delete_existing:
        console.print("[yellow]Deleting existing products...[/yellow]")
        existing = odoo.search(
            "product.product", [("default_code", "like", f"{set_code.lower()}-")]
        )
        if existing:
            odoo.unlink("product.product", existing)
            console.print(f"[yellow]Deleted {len(existing)} existing products[/yellow]")

    # STEP 1: Check which products already exist (to avoid unnecessary image downloads)
    # Use the correct SKU prefix for this set
    sku_prefix = SKU_PREFIXES.get(set_code.lower(), set_code.lower())
    console.print(f"[dim]Checking existing products with prefix: {sku_prefix}-[/dim]")
    existing_skus: set[str] = set()
    existing_products = odoo.search_read(
        "product.product",
        [("default_code", "like", f"{sku_prefix}-")],
        ["default_code"],
    )
    for p in existing_products:
        if p.get("default_code"):
            existing_skus.add(p["default_code"].lower())
    console.print(f"[dim]Found {len(existing_skus)} existing products[/dim]")

    # STEP 2: Identify NEW cards that need images
    new_cards = []
    update_cards = []
    for card in cards:
        ext_number = card.get("extNumber", "").strip()
        variant = card.get("subTypeName", "Normal") or "Normal"
        match = re.search(r"(\d+)", ext_number)
        card_number = match.group(1) if match else ext_number
        sku = generate_sku(set_code, card_number, variant)

        if sku.lower() in existing_skus:
            update_cards.append(card)
        else:
            new_cards.append(card)

    console.print(f"[green]New cards to create: {len(new_cards)}[/green]")
    console.print(f"[blue]Existing cards to update prices: {len(update_cards)}[/blue]")

    # STEP 3: Only download images for NEW cards
    image_cache: dict[str, str] = {}
    if new_cards and not skip_images:
        image_cache = download_images_parallel(new_cards)
    elif not new_cards:
        console.print("[dim]No new cards - skipping image downloads[/dim]")

    # Process cards
    stats = {"created": 0, "updated": 0, "skipped": 0, "errors": 0}

    # Get next barcode sequence number (only needed if creating new products)
    next_barcode_seq = get_next_sequence(odoo) if new_cards else 0
    if new_cards:
        console.print(f"[blue]Starting barcode sequence: {next_barcode_seq}[/blue]")

    # STEP 4: Update existing products (price only - fast!)
    if update_cards:
        console.print(f"[blue]Updating {len(update_cards)} existing products...[/blue]")
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Updating prices...", total=len(update_cards))

            for card in update_cards:
                progress.update(task, advance=1)
                ext_number = card.get("extNumber", "").strip()
                variant = card.get("subTypeName", "Normal") or "Normal"
                match = re.search(r"(\d+)", ext_number)
                card_number = match.group(1) if match else ext_number
                sku = generate_sku(set_code, card_number, variant)

                try:
                    price = float(card.get("marketPrice") or card.get("midPrice") or 0)
                except (ValueError, TypeError):
                    price = 0.0

                existing = odoo.get_product_by_sku(sku)
                if existing:
                    try:
                        odoo.write("product.product", [existing["id"]], {"list_price": price})
                        stats["updated"] += 1
                    except Exception as e:
                        logger.error(f"Failed to update {sku}: {e}")
                        stats["errors"] += 1

    # STEP 5: Create new products (with full data + images)
    if new_cards:
        console.print(f"[green]Creating {len(new_cards)} new products...[/green]")
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Creating products...", total=len(new_cards))

            for card in new_cards:
                progress.update(task, advance=1)

                name = card.get("name", "Unknown")
                ext_number = card.get("extNumber", "").strip()
                rarity = card.get("extRarity", "")
                variant = card.get("subTypeName", "Normal") or "Normal"

                match = re.search(r"(\d+)", ext_number)
                card_number = match.group(1) if match else ext_number

                try:
                    price = float(card.get("marketPrice") or card.get("midPrice") or 0)
                except (ValueError, TypeError):
                    price = 0.0

                sku = generate_sku(set_code, card_number, variant)
                display_name = generate_display_name(name, card_number, variant)

                product_data = {
                    "name": display_name,
                    "default_code": sku,
                    "list_price": price,
                    "categ_id": category_id,
                    "type": "product",
                    "sale_ok": True,
                    "purchase_ok": True,
                }

                # Add image from cache
                if card_number in image_cache:
                    product_data["image_1920"] = image_cache[card_number]

                # Store rarity and set name in description
                description_parts = []
                if rarity:
                    description_parts.append(f"Rarity: {rarity}")
                if set_name:
                    description_parts.append(f"Set: {set_name}")
                if description_parts:
                    product_data["description"] = "\n".join(description_parts)

                try:
                    barcode = generate_ean13(next_barcode_seq)
                    next_barcode_seq += 1
                    product_data["barcode"] = barcode
                    odoo.create("product.product", product_data)
                    stats["created"] += 1
                except Exception as e:
                    logger.error(f"Failed to create {sku}: {e}")
                    stats["errors"] += 1

    console.print("\n[bold green]Import complete![/bold green]")
    console.print(f"  Created: {stats['created']}")
    console.print(f"  Updated: {stats['updated']}")
    console.print(f"  Skipped: {stats['skipped']}")
    console.print(f"  Errors: {stats['errors']}")

    # Record price history (silently skips if DB not accessible)
    if init_price_history_table():
        price_records = []
        for card in cards:
            ext_number = card.get("extNumber", "").strip()
            variant = card.get("subTypeName", "Normal") or "Normal"
            match = re.search(r"(\d+)", ext_number)
            card_number = match.group(1) if match else ext_number
            sku = generate_sku(set_code, card_number, variant)

            try:
                price = float(card.get("marketPrice") or card.get("midPrice") or 0)
            except (ValueError, TypeError):
                price = 0.0

            price_records.append(
                {
                    "sku": sku,
                    "price": price,
                    "low_price": _parse_price(card.get("lowPrice")),
                    "mid_price": _parse_price(card.get("midPrice")),
                    "high_price": _parse_price(card.get("highPrice")),
                    "market_price": _parse_price(card.get("marketPrice")),
                }
            )

        recorded = record_prices_batch(price_records)
        if recorded > 0:
            console.print(f"[green]Recorded {recorded} price history entries[/green]")

    return stats


def _parse_price(value: Any) -> float | None:
    """Safely parse a price value."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def import_all_sets(
    dry_run: bool = False,
    skip_images: bool = False,
) -> dict[str, Any]:
    """
    Import all downloaded sets into Odoo.

    Args:
        dry_run: If True, don't actually create products
        skip_images: If True, don't download images

    Returns:
        Summary of import results
    """
    available = get_available_sets()
    if not available:
        console.print("[red]No CSVs found. Run 'tcg download --all' first.[/red]")
        return {"error": "No CSVs found"}

    console.print(f"[bold green]Importing {len(available)} sets...[/bold green]")

    all_stats = {"sets": 0, "created": 0, "updated": 0, "errors": 0}

    for set_code in sorted(available.keys()):
        console.print(f"\n{'=' * 60}")
        result = import_set(set_code, dry_run=dry_run, skip_images=skip_images)
        if "error" not in result:
            all_stats["sets"] += 1
            all_stats["created"] += result.get("created", 0)
            all_stats["updated"] += result.get("updated", 0)
            all_stats["errors"] += result.get("errors", 0)

    console.print(f"\n{'=' * 60}")
    console.print("[bold green]All imports complete![/bold green]")
    console.print(f"  Sets imported: {all_stats['sets']}")
    console.print(f"  Total created: {all_stats['created']}")
    console.print(f"  Total updated: {all_stats['updated']}")
    console.print(f"  Total errors: {all_stats['errors']}")    return all_stats
