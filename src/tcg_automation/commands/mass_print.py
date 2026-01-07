"""
Mass print labels for cards in stock.

Prints labels for all products with quantity > 0,
printing one label per unit in stock.
"""

import logging
import sys
from typing import Any

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

from ..odoo_client import get_odoo_client
from .import_set import SET_MAPPINGS

logger = logging.getLogger(__name__)
console = Console()


def get_full_set_name(set_code: str) -> str:
    """Convert a set code to full display name.

    E.g., "sv09" -> "SV09: Journey Together"
    """
    code_lower = set_code.lower()
    if code_lower in SET_MAPPINGS:
        return f"{set_code.upper()}: {SET_MAPPINGS[code_lower]['name']}"
    return set_code.upper()


def get_products_in_stock(
    odoo,
    set_code: str | None = None,
    min_qty: int = 1,
) -> list[dict]:
    """
    Get products with stock quantity >= min_qty.

    Args:
        odoo: Odoo client instance
        set_code: Optional set code to filter by
        min_qty: Minimum quantity to include (default 1)

    Returns:
        List of products with their stock quantities
    """
    # Build domain for products with SKU
    domain = [("default_code", "!=", False)]

    if set_code:
        domain.append(("default_code", "like", f"{set_code.lower()}-"))

    # Get products with relevant fields (x_set_name may not exist in all Odoo instances)
    try:
        products = odoo.search_read(
            "product.product",
            domain,
            ["id", "name", "default_code", "list_price", "barcode", "qty_available", "x_set_name"],
        )
        has_set_name_field = True
    except Exception as e:
        if "x_set_name" in str(e):
            # Field doesn't exist, query without it
            products = odoo.search_read(
                "product.product",
                domain,
                ["id", "name", "default_code", "list_price", "barcode", "qty_available"],
            )
            has_set_name_field = False
        else:
            raise

    # Filter to products with stock
    in_stock = []
    for p in products:
        qty = int(p.get("qty_available", 0))
        if qty >= min_qty:
            # Extract set name from SKU if x_set_name not available
            sku = p.get("default_code", "")
            set_name = ""
            if has_set_name_field:
                set_name = p.get("x_set_name", "") or ""
            if not set_name and sku:
                # Try to extract from SKU (e.g., "sv09-001" -> "SV09: Journey Together")
                parts = sku.split("-")
                if parts:
                    set_name = get_full_set_name(parts[0])

            in_stock.append(
                {
                    "id": p["id"],
                    "name": p["name"],
                    "sku": sku,
                    "price": p.get("list_price", 0.0),
                    "barcode": p.get("barcode", ""),
                    "qty": qty,
                    "set_name": set_name,
                }
            )

    return in_stock


def mass_print_labels(
    set_code: str | None = None,
    dry_run: bool = False,
    limit: int | None = None,
) -> dict[str, Any]:
    """
    Print labels for all products in stock.

    For each product, prints N labels where N = stock quantity.

    Args:
        set_code: Optional set code to filter by
        dry_run: If True, show what would be printed without actually printing
        limit: Optional limit on total labels to print

    Returns:
        Summary of print results
    """
    odoo = get_odoo_client()
    if not odoo.connect():
        return {"error": "Failed to connect to Odoo"}

    # Get products in stock
    console.print("[blue]Fetching products in stock...[/blue]")
    products = get_products_in_stock(odoo, set_code)

    if not products:
        console.print("[yellow]No products with stock found[/yellow]")
        return {"printed": 0, "products": 0}

    # Calculate totals
    total_products = len(products)
    total_labels = sum(p["qty"] for p in products)

    if limit and total_labels > limit:
        console.print(f"[yellow]Limiting to {limit} labels (of {total_labels} total)[/yellow]")

    console.print("\n[bold]Stock Summary:[/bold]")
    console.print(f"  Products with stock: {total_products}")
    console.print(f"  Total labels to print: {total_labels}")

    if set_code:
        console.print(f"  Set filter: {set_code.upper()}")

    # Show preview table
    table = Table(title="\nLabels to Print", show_lines=False)
    table.add_column("SKU", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Set", style="yellow")
    table.add_column("Qty", justify="right", style="green")
    table.add_column("BC", style="dim")  # Barcode status

    labels_shown = 0
    for p in sorted(products, key=lambda x: x["sku"])[:20]:  # Show first 20
        barcode_status = "✓" if p["barcode"] else "✗"
        # Truncate set name for display
        set_display = p["set_name"][:20] if p["set_name"] else "-"
        table.add_row(p["sku"], p["name"][:35], set_display, str(p["qty"]), barcode_status)
        labels_shown += 1

    if total_products > 20:
        table.add_row("...", f"({total_products - 20} more)", "", "", "")

    console.print(table)

    if dry_run:
        console.print("\n[yellow]DRY RUN - no labels will be printed[/yellow]")
        return {
            "products": total_products,
            "total_labels": total_labels,
            "printed": 0,
            "dry_run": True,
        }

    # Check for products without barcodes
    no_barcode = [p for p in products if not p["barcode"]]
    if no_barcode:
        console.print(f"\n[yellow]⚠ {len(no_barcode)} products have no barcode![/yellow]")
        console.print("[yellow]Run 'tcg barcodes backfill' first to generate barcodes.[/yellow]")
        return {"error": "Products missing barcodes. Run 'tcg barcodes backfill' first."}

    # Import printer service (lazy import to avoid circular deps)
    try:
        # Add backend to path if needed
        import os

        backend_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "backend")
        if backend_path not in sys.path:
            sys.path.insert(0, os.path.abspath(backend_path))

        from app.services.printer import get_printer_service

        printer = get_printer_service()
    except ImportError as e:
        console.print(f"[red]Failed to import printer service: {e}[/red]")
        return {"error": f"Printer service not available: {e}"}

    if not printer.is_available:
        console.print("[red]Printer not configured or disabled[/red]")
        return {"error": "Printer not available"}

    if not printer.check_connection():
        console.print("[red]Cannot connect to printer[/red]")
        return {"error": "Printer connection failed"}

    console.print("\n[green]Printer connected. Starting print job...[/green]")

    # Print labels
    printed = 0
    failed = 0
    errors = []
    labels_remaining = limit if limit else float("inf")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        task = progress.add_task(
            "Printing labels...", total=min(total_labels, limit or total_labels)
        )

        for product in products:
            if labels_remaining <= 0:
                break

            qty_to_print = min(product["qty"], int(labels_remaining))

            # Determine variant from SKU
            variant = None
            sku = product["sku"]
            if "-holo" in sku.lower():
                variant = "Holofoil"
            elif "-reverse" in sku.lower():
                variant = "Reverse Holofoil"

            for i in range(qty_to_print):
                success, msg = printer.print_label(
                    sku=sku,
                    name=product["name"],
                    price=product["price"],
                    set_name=product["set_name"],
                    variant=variant,
                    barcode=product["barcode"],
                )

                if success:
                    printed += 1
                else:
                    failed += 1
                    errors.append(f"{sku}: {msg}")

                progress.update(task, advance=1)
                labels_remaining -= 1

                if labels_remaining <= 0:
                    break

    # Summary
    console.print("\n[bold green]Print job complete![/bold green]")
    console.print(f"  Printed: {printed}")
    if failed:
        console.print(f"  [red]Failed: {failed}[/red]")
        for err in errors[:5]:
            console.print(f"    - {err}")
        if len(errors) > 5:
            console.print(f"    ... and {len(errors) - 5} more errors")

    return {
        "products": total_products,
        "total_labels": total_labels,
        "printed": printed,
        "failed": failed,
        "errors": errors,
    }
