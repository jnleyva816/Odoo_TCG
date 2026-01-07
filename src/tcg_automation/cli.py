"""
TCG Automation CLI
==================
Unified command-line interface for all TCG automation tasks.

Usage:
    tcg import sv09           # Import a set
    tcg sync                  # Sync all prices
    tcg server                # Start card scanner
    tcg labels ME02-001       # Generate a label
"""

import logging
import sys

import click
from rich.console import Console
from rich.logging import RichHandler

from . import __version__

console = Console()


def setup_logging(verbose: bool = False):
    """Configure logging with rich output."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, show_time=False, show_path=False)],
    )


@click.group()
@click.version_option(version=__version__, prog_name="tcg")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
@click.pass_context
def main(ctx, verbose):
    """TCG Automation - Pokemon card inventory management for Odoo."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    setup_logging(verbose)


# =============================================================================
# IMPORT COMMAND
# =============================================================================


@main.command()
@click.argument("set_code")
@click.option("--dry-run", is_flag=True, help="Show what would be imported without making changes")
@click.option("--delete-existing", is_flag=True, help="Delete existing products before import")
@click.option("--skip-images", is_flag=True, help="Skip downloading card images")
def import_set(set_code, dry_run, delete_existing, skip_images):
    """
    Import a card set from tcgcsv.com.

    SET_CODE: The set code (e.g., sv09, me02, sv03)

    Examples:
        tcg import sv09
        tcg import me02 --dry-run
        tcg import sv03 --delete-existing
    """
    from .commands.import_set import SET_MAPPINGS
    from .commands.import_set import import_set as do_import

    if set_code.lower() == "list":
        console.print("[bold]Available sets:[/bold]")
        for code, info in SET_MAPPINGS.items():
            console.print(f"  {code.upper():6} - {info['name']}")
        return

    result = do_import(set_code, dry_run, delete_existing, skip_images)

    if "error" in result:
        console.print(f"[red]Error: {result['error']}[/red]")
        sys.exit(1)


@main.command(name="list-sets")
def list_sets():
    """List all available sets that can be imported."""
    from .commands.import_set import SET_MAPPINGS

    console.print("[bold]Available sets:[/bold]\n")
    for code, info in sorted(SET_MAPPINGS.items()):
        console.print(
            f"  [cyan]{code.upper():6}[/cyan] - {info['name']} (Group ID: {info['group_id']})"
        )


# =============================================================================
# SYNC COMMAND
# =============================================================================


@main.command()
@click.option("--dry-run", is_flag=True, help="Show price changes without updating")
@click.option("--set", "set_code", help="Only sync a specific set")
def sync(dry_run, set_code):
    """
    Sync prices from tcgcsv.com.

    Updates prices for all sets found in Odoo, or a specific set if --set is provided.

    Examples:
        tcg sync
        tcg sync --dry-run
        tcg sync --set sv09
    """
    from .commands.sync_prices import sync_all_prices, sync_set_prices

    if set_code:
        result = sync_set_prices(set_code, dry_run)
        if "error" in result:
            console.print(f"[red]Error: {result['error']}[/red]")
            sys.exit(1)
        console.print(f"[green]Updated {result.get('updated', 0)} prices[/green]")
    else:
        result = sync_all_prices(dry_run)
        if "error" in result:
            console.print(f"[red]Error: {result['error']}[/red]")
            sys.exit(1)


# =============================================================================
# SERVER COMMAND
# =============================================================================


@main.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", default=5000, type=int, help="Port to listen on")
@click.option("--no-debug", is_flag=True, help="Disable debug mode")
def server(host, port, no_debug):
    """
    Start the card scanner web server.

    Opens a web interface for scanning cards into inventory and printing labels.

    Examples:
        tcg server
        tcg server --port 8080
        tcg server --host 127.0.0.1 --no-debug
    """
    from .commands.server import run_server

    run_server(host, port, debug=not no_debug)


# =============================================================================
# LABELS COMMAND
# =============================================================================


@main.command()
@click.argument("skus", nargs=-1)
@click.option("-o", "--output", default="labels.pdf", help="Output PDF file")
@click.option("--set", "set_code", help="Generate labels for all cards in a set")
def labels(skus, output, set_code):
    """
    Generate labels for cards.

    SKUS: One or more SKUs to generate labels for

    Examples:
        tcg labels me02-001 me02-002
        tcg labels --set sv09 -o sv09_labels.pdf
    """
    from .commands.labels import generate_labels_pdf
    from .odoo_client import get_odoo_client

    odoo = get_odoo_client()
    if not odoo.connect():
        console.print("[red]Failed to connect to Odoo[/red]")
        sys.exit(1)

    products = []

    if set_code:
        # Get all products for the set
        all_products = odoo.search_read(
            "product.product",
            [("default_code", "like", f"{set_code.lower()}-")],
            ["id", "name", "default_code"],
        )
        products.extend(all_products)
        console.print(f"[green]Found {len(products)} products in {set_code.upper()}[/green]")
    else:
        for sku in skus:
            product = odoo.get_product_by_sku(sku)
            if product:
                products.append(product)
            else:
                console.print(f"[yellow]Product not found: {sku}[/yellow]")

    if not products:
        console.print("[red]No products to generate labels for[/red]")
        sys.exit(1)

    output_path = generate_labels_pdf(products, output)
    console.print(f"[green]Generated {len(products)} labels: {output_path}[/green]")


# =============================================================================
# PRINT COMMAND
# =============================================================================


@main.group()
def print_labels():
    """Print labels for cards."""
    pass


@print_labels.command(name="stock")
@click.option("--set", "set_code", help="Only print labels for a specific set")
@click.option("--dry-run", is_flag=True, help="Show what would be printed without printing")
@click.option("--limit", type=int, help="Limit total number of labels to print")
def print_stock(set_code, dry_run, limit):
    """
    Print labels for all cards in stock.

    Prints one label per unit in stock. If you have 3 copies of a card,
    it will print 3 labels.

    Examples:
        tcg print-labels stock --dry-run          # Preview what will print
        tcg print-labels stock                    # Print all labels
        tcg print-labels stock --set sv09         # Only print for SV09 set
        tcg print-labels stock --limit 50         # Print max 50 labels
    """
    from .commands.mass_print import mass_print_labels

    result = mass_print_labels(set_code=set_code, dry_run=dry_run, limit=limit)

    if "error" in result:
        console.print(f"[red]Error: {result['error']}[/red]")
        sys.exit(1)


# =============================================================================
# BARCODES COMMAND
# =============================================================================


@main.group()
def barcodes():
    """Manage product barcodes (EAN-13)."""
    pass


@barcodes.command(name="backfill")
@click.option("--dry-run", is_flag=True, help="Show what would be done without making changes")
@click.option("--set", "set_code", help="Only process products from a specific set")
@click.option("--force", is_flag=True, help="Regenerate barcodes even for products that have them")
def barcodes_backfill(dry_run, set_code, force):
    """
    Add EAN-13 barcodes to existing products that don't have them.

    Examples:
        tcg barcodes backfill
        tcg barcodes backfill --set sv09
        tcg barcodes backfill --dry-run
        tcg barcodes backfill --force  # Regenerate all
    """
    from .commands.barcodes import backfill_barcodes

    result = backfill_barcodes(dry_run=dry_run, set_code=set_code, force=force)

    if "error" in result:
        console.print(f"[red]Error: {result['error']}[/red]")
        sys.exit(1)


@barcodes.command(name="verify")
@click.option("--set", "set_code", help="Only check products from a specific set")
def barcodes_verify(set_code):
    """
    Verify barcode coverage and validity.

    Examples:
        tcg barcodes verify
        tcg barcodes verify --set sv09
    """
    from .commands.barcodes import verify_barcodes

    result = verify_barcodes(set_code=set_code)

    if "error" in result:
        console.print(f"[red]Error: {result['error']}[/red]")
        sys.exit(1)


# =============================================================================
# STATUS COMMAND
# =============================================================================


@main.command()
def status():
    """Check Odoo connection status."""
    from .config import get_config
    from .odoo_client import get_odoo_client

    config = get_config()

    console.print("[bold]TCG Automation Status[/bold]\n")
    console.print(f"Odoo URL: {config.odoo.url}")
    console.print(f"Database: {config.odoo.db}")
    console.print(f"User: {config.odoo.user}")

    odoo = get_odoo_client()
    if odoo.connect():
        console.print("\n[green]Connection: OK[/green]")

        # Count products
        count = len(odoo.search("product.product", [("default_code", "!=", False)]))
        console.print(f"Products with SKU: {count}")
    else:
        console.print("\n[red]Connection: FAILED[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
