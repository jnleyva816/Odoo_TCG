"""
Sync prices from local CSVs or tcgcsv.com for all sets in Odoo.

Workflow:
1. Download fresh CSV (saves to csvs/{set_code}/{date}_ProductsAndPrices.csv)
2. Compare prices with Odoo products
3. Update changed prices
"""

import csv
import logging
import re
from collections import defaultdict
from pathlib import Path

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

from ..odoo_client import get_odoo_client
from .download import CSV_BASE_DIR, SET_CODE_ALIASES, download_set_csv, get_all_pokemon_sets

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


def load_prices_from_csv(csv_path: Path) -> dict[str, float]:
    """
    Load prices from a CSV file.

    Returns:
        Dict mapping SKU to market price
    """
    with open(csv_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    price_lookup: dict[str, float] = {}

    for row in rows:
        ext_number = row.get("extNumber", "").strip()
        if not ext_number:
            continue

        # Extract card number
        match = re.search(r"(\d+)", ext_number)
        if not match:
            continue
        card_num = match.group(1).zfill(3)

        # Get variant
        variant = row.get("subTypeName", "Normal") or "Normal"
        if variant not in ("Normal", "Holofoil", "Reverse Holofoil"):
            continue

        # Get the set code from the CSV path (folder name)
        set_code = csv_path.parent.name.lower()

        # Build SKU
        sku = f"{set_code}-{card_num}"
        if variant == "Holofoil":
            sku += "-holo"
        elif variant == "Reverse Holofoil":
            sku += "-reverse"

        # Get price
        try:
            price = float(row.get("marketPrice") or row.get("midPrice") or 0)
        except (ValueError, TypeError):
            price = 0.0

        if price > 0:
            price_lookup[sku] = price

    return price_lookup


def sync_set_prices(set_code: str, dry_run: bool = False, download_fresh: bool = True) -> dict:
    """
    Sync prices for a single set.

    Args:
        set_code: Set code (e.g., 'sv03')
        dry_run: If True, don't update Odoo
        download_fresh: If True, download fresh CSV first

    Returns:
        Stats dict with updated/skipped/errors
    """
    set_code = set_code.lower()

    # Download fresh CSV if requested
    if download_fresh:
        console.print(f"[blue]Downloading fresh prices for {set_code.upper()}...[/blue]")

        # Get group ID
        if set_code in SET_CODE_ALIASES:
            group_id = SET_CODE_ALIASES[set_code]
        else:
            # Try to find in API
            all_sets = get_all_pokemon_sets()
            sets_by_abbr = {s.get("abbreviation", "").lower(): s for s in all_sets}
            if set_code in sets_by_abbr:
                group_id = sets_by_abbr[set_code]["groupId"]
            else:
                return {"error": f"Unknown set: {set_code}"}

        result = download_set_csv(group_id, set_code)
        if not result:
            return {"error": f"Failed to download {set_code}"}

        csv_path, row_count = result
        console.print(f"[green]Downloaded {row_count} rows[/green]")
    else:
        # Use existing CSV
        set_dir = CSV_BASE_DIR / set_code
        if not set_dir.exists():
            return {"error": f"No CSV found for {set_code}. Run 'tcg download {set_code}' first."}

        csv_files = sorted(set_dir.glob("*_ProductsAndPrices.csv"), reverse=True)
        if not csv_files:
            return {"error": f"No CSV found for {set_code}"}

        csv_path = csv_files[0]
        console.print(f"[dim]Using: {csv_path.name}[/dim]")

    # Load prices from CSV
    price_lookup = load_prices_from_csv(csv_path)
    console.print(f"[green]Found {len(price_lookup)} prices in CSV[/green]")

    # Connect to Odoo
    odoo = get_odoo_client()
    if not odoo.connect():
        return {"error": "Failed to connect to Odoo"}

    # Update prices
    stats = {"updated": 0, "skipped": 0, "not_found": 0, "errors": 0}
    changes = []

    for sku, new_price in price_lookup.items():
        product = odoo.get_product_by_sku(sku)
        if not product:
            stats["not_found"] += 1
            continue

        current_price = product.get("list_price", 0)

        # Skip if price hasn't changed (within 1 cent)
        if abs(current_price - new_price) < 0.01:
            stats["skipped"] += 1
            continue

        # Track change
        changes.append({
            "sku": sku,
            "name": product.get("name", ""),
            "old": current_price,
            "new": new_price,
            "id": product["id"],
        })

    # Show changes
    if changes:
        console.print(f"\n[bold]Price changes ({len(changes)}):[/bold]")
        for c in changes[:20]:
            diff = c["new"] - c["old"]
            color = "green" if diff > 0 else "red"
            console.print(
                f"  {c['sku']}: ${c['old']:.2f} → ${c['new']:.2f} "
                f"([{color}]{diff:+.2f}[/{color}])"
            )
        if len(changes) > 20:
            console.print(f"  ... and {len(changes) - 20} more")

    # Apply changes
    if not dry_run and changes:
        console.print(f"\n[blue]Updating {len(changes)} prices in Odoo...[/blue]")
        for c in changes:
            try:
                odoo.write("product.product", [c["id"]], {"list_price": c["new"]})
                stats["updated"] += 1
            except Exception as e:
                logger.error(f"Failed to update {c['sku']}: {e}")
                stats["errors"] += 1
    elif dry_run:
        stats["updated"] = len(changes)
        console.print(f"\n[yellow]DRY RUN - {len(changes)} prices would be updated[/yellow]")
    else:
        console.print("\n[green]No price changes needed[/green]")

    return stats


def sync_all_prices(dry_run: bool = False, download_fresh: bool = True) -> dict:
    """
    Sync prices for all sets in Odoo.

    Args:
        dry_run: If True, don't update Odoo
        download_fresh: If True, download fresh CSVs first

    Returns:
        Total stats dict
    """
    console.print("[bold blue]TCG Price Sync[/bold blue]")
    console.print("-" * 40)

    # Discover sets in Odoo
    sets = discover_sets()
    if not sets:
        console.print("[red]No sets found in Odoo[/red]")
        return {"error": "No sets found"}

    console.print(f"[green]Found {len(sets)} sets in Odoo[/green]")
    for code, products in sorted(sets.items()):
        console.print(f"  {code.upper()}: {len(products)} products")

    if dry_run:
        console.print("\n[yellow]DRY RUN - no changes will be made[/yellow]")

    total_stats = {"updated": 0, "skipped": 0, "not_found": 0, "errors": 0}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Syncing prices...", total=len(sets))

        for set_code in sorted(sets.keys()):
            progress.update(task, description=f"Syncing {set_code.upper()}...")

            result = sync_set_prices(set_code, dry_run=dry_run, download_fresh=download_fresh)

            if "error" in result:
                console.print(f"[yellow]{set_code.upper()}: {result['error']}[/yellow]")
                total_stats["errors"] += 1
            else:
                total_stats["updated"] += result.get("updated", 0)
                total_stats["skipped"] += result.get("skipped", 0)
                total_stats["not_found"] += result.get("not_found", 0)
                total_stats["errors"] += result.get("errors", 0)

            progress.update(task, advance=1)

    console.print("\n" + "=" * 40)
    console.print("[bold green]Sync complete![/bold green]")
    console.print(f"  Updated: {total_stats['updated']}")
    console.print(f"  Unchanged: {total_stats['skipped']}")
    console.print(f"  Not in Odoo: {total_stats['not_found']}")
    console.print(f"  Errors: {total_stats['errors']}")

    return total_stats
