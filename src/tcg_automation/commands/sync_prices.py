"""
Sync prices from tcgcsv.com for all sets in Odoo.
"""

import csv
import io
import logging
import re
from collections import defaultdict

import requests
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..odoo_client import get_odoo_client
from .import_set import SET_MAPPINGS

logger = logging.getLogger(__name__)
console = Console()


def discover_sets() -> dict[str, list[int]]:
    """Discover all sets in Odoo by scanning product SKUs."""
    odoo = get_odoo_client()
    if not odoo.connect():
        return {}

    products = odoo.search_read(
        "product.product",
        [("default_code", "!=", False)],
        ["default_code"],
    )

    sets: dict[str, list[int]] = defaultdict(list)
    for p in products:
        sku = p.get("default_code", "")
        if "-" in sku:
            prefix = sku.split("-")[0].lower()
            sets[prefix].append(p["id"])

    return dict(sets)


def sync_set_prices(set_code: str, dry_run: bool = False) -> dict:
    """Sync prices for a single set."""
    if set_code.lower() not in SET_MAPPINGS:
        return {"error": f"Unknown set mapping for {set_code}"}

    set_info = SET_MAPPINGS[set_code.lower()]
    group_id = set_info["group_id"]

    # Fetch prices
    prices_url = f"https://tcgcsv.com/{group_id}/prices"
    try:
        resp = requests.get(prices_url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        return {"error": f"Failed to fetch prices: {e}"}

    prices = list(csv.DictReader(io.StringIO(resp.text)))

    # Build price lookup by extNumber and variant
    price_lookup: dict[str, float] = {}
    for p in prices:
        variant = p.get("subTypeName", "")
        if variant not in ("Normal", "Holofoil", "Reverse Holofoil"):
            continue

        ext_number = p.get("extNumber", "")
        match = re.search(r"(\d+)", ext_number)
        if not match:
            continue
        card_num = match.group(1).zfill(3)

        # Build SKU
        sku = f"{set_code.lower()}-{card_num}"
        if variant == "Holofoil":
            sku += "-holo"
        elif variant == "Reverse Holofoil":
            sku += "-reverse"

        price = float(p.get("marketPrice") or p.get("midPrice") or 0)
        if price > 0:
            price_lookup[sku] = price

    # Update Odoo
    odoo = get_odoo_client()
    stats = {"updated": 0, "skipped": 0, "not_found": 0}

    for sku, price in price_lookup.items():
        product = odoo.get_product_by_sku(sku)
        if not product:
            stats["not_found"] += 1
            continue

        current_price = product.get("list_price", 0)
        if abs(current_price - price) < 0.01:
            stats["skipped"] += 1
            continue

        if not dry_run:
            odoo.write("product.product", [product["id"]], {"list_price": price})

        stats["updated"] += 1
        logger.debug(f"Updated {sku}: ${current_price:.2f} -> ${price:.2f}")

    return stats


def sync_all_prices(dry_run: bool = False) -> dict:
    """Sync prices for all discovered sets."""
    console.print("[bold blue]TCG Price Sync[/bold blue]")
    console.print("-" * 40)

    # Discover sets
    sets = discover_sets()
    if not sets:
        console.print("[red]No sets found in Odoo[/red]")
        return {"error": "No sets found"}

    console.print(f"[green]Found {len(sets)} sets in Odoo[/green]")
    for code, products in sets.items():
        console.print(f"  {code.upper()}: {len(products)} products")

    if dry_run:
        console.print("\n[yellow]DRY RUN - no changes will be made[/yellow]")

    total_stats = {"updated": 0, "skipped": 0, "not_found": 0, "errors": 0}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Syncing prices...", total=len(sets))

        for set_code in sets:
            progress.update(task, description=f"Syncing {set_code.upper()}...")

            if set_code not in SET_MAPPINGS:
                console.print(f"[yellow]Skipping {set_code} - no mapping defined[/yellow]")
                progress.update(task, advance=1)
                continue

            result = sync_set_prices(set_code, dry_run)

            if "error" in result:
                console.print(f"[red]{set_code}: {result['error']}[/red]")
                total_stats["errors"] += 1
            else:
                total_stats["updated"] += result.get("updated", 0)
                total_stats["skipped"] += result.get("skipped", 0)
                total_stats["not_found"] += result.get("not_found", 0)

            progress.update(task, advance=1)

    console.print(f"\n[bold green]Sync complete![/bold green]")
    console.print(f"  Updated: {total_stats['updated']}")
    console.print(f"  Unchanged: {total_stats['skipped']}")
    console.print(f"  Not found: {total_stats['not_found']}")
    console.print(f"  Errors: {total_stats['errors']}")

    return total_stats


