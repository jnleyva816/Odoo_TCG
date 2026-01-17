"""
TCG Automation CLI
==================
Unified command-line interface for all TCG automation tasks.

Usage:
    tcg download sv09         # Download CSV for a set
    tcg download --all        # Download all Pokemon sets
    tcg import sv09           # Import a set from CSV
    tcg import --all          # Import all downloaded sets
    tcg sync                  # Sync all prices (download + update)
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
# DOWNLOAD COMMAND
# =============================================================================


@main.command()
@click.argument("set_codes", nargs=-1)
@click.option("--all", "download_all", is_flag=True, help="Download all Pokemon sets")
def download(set_codes, download_all):
    """
    Download card set CSVs from tcgcsv.com.

    Downloads CSVs and organizes them by set and date for historical pricing:
        csvs/sv09/2026-01-16_ProductsAndPrices.csv

    SET_CODES: One or more set codes to download (e.g., sv09 sv08)

    Examples:
        tcg download sv09              # Download one set
        tcg download sv09 sv08 me02    # Download multiple sets
        tcg download --all             # Download ALL Pokemon sets
    """
    from .commands.download import download_sets, list_downloaded_sets

    if not set_codes and not download_all:
        # Show what's already downloaded
        downloaded = list_downloaded_sets()
        if downloaded:
            console.print("[bold]Downloaded sets:[/bold]\n")
            for info in downloaded:
                console.print(
                    f"  [cyan]{info['set_code'].upper():6}[/cyan] - "
                    f"{info['count']} snapshots, latest: {info['latest']}"
                )
            console.print("\n[dim]Use 'tcg download <set_code>' or 'tcg download --all'[/dim]")
        else:
            console.print("[yellow]No CSVs downloaded yet.[/yellow]")
            console.print("[dim]Use 'tcg download --all' to download all Pokemon sets[/dim]")
        return

    result = download_sets(
        set_codes=list(set_codes) if set_codes else None,
        download_all=download_all,
    )

    if "error" in result:
        console.print(f"[red]Error: {result['error']}[/red]")
        sys.exit(1)


# =============================================================================
# IMPORT COMMAND
# =============================================================================


@main.command(name="import")
@click.argument("set_code", required=False)
@click.option("--all", "import_all", is_flag=True, help="Import all downloaded sets")
@click.option("--dry-run", is_flag=True, help="Show what would be imported without making changes")
@click.option("--delete-existing", is_flag=True, help="Delete existing products before import")
@click.option("--skip-images", is_flag=True, help="Skip downloading card images")
def import_cmd(set_code, import_all, dry_run, delete_existing, skip_images):
    """
    Import card sets from downloaded CSVs into Odoo.

    Reads from csvs/{set_code}/ folder (latest CSV file).
    Run 'tcg download' first to get the CSV files.

    SET_CODE: The set code (e.g., sv09, me02, sv03)

    Examples:
        tcg import sv09              # Import one set
        tcg import sv09 --dry-run    # Preview what would be imported
        tcg import --all             # Import all downloaded sets
        tcg import --all --skip-images  # Import all without downloading images
    """
    from .commands.import_set import get_available_sets
    from .commands.import_set import import_all_sets as do_import_all
    from .commands.import_set import import_set as do_import

    if import_all:
        result = do_import_all(dry_run=dry_run, skip_images=skip_images)
    elif set_code:
        result = do_import(set_code, dry_run, delete_existing, skip_images)
    else:
        # Show available sets
        available = get_available_sets()
        if available:
            console.print("[bold]Available sets to import:[/bold]\n")
            for code, info in sorted(available.items()):
                console.print(
                    f"  [cyan]{code.upper():6}[/cyan] - {info['csv_count']} CSVs, "
                    f"latest: {info['latest'].name}"
                )
            console.print("\n[dim]Use 'tcg import <set_code>' or 'tcg import --all'[/dim]")
        else:
            console.print("[yellow]No CSVs found. Run 'tcg download --all' first.[/yellow]")
        return

    if "error" in result:
        console.print(f"[red]Error: {result['error']}[/red]")
        sys.exit(1)


@main.command(name="list-sets")
def list_sets():
    """List all Pokemon sets available to download from tcgcsv.com."""
    from .commands.download import get_all_pokemon_sets

    console.print("[bold]Fetching available sets from tcgcsv.com...[/bold]\n")
    sets = get_all_pokemon_sets()

    # Show recent sets (with abbreviation)
    recent = [s for s in sets if s.get("abbreviation")]
    console.print(f"[bold]Available sets ({len(recent)} with codes):[/bold]\n")
    for s in sorted(recent, key=lambda x: x["groupId"], reverse=True)[:30]:
        abbr = s.get("abbreviation", "").lower()
        name = s.get("name", "Unknown")
        gid = s.get("groupId")
        console.print(f"  [cyan]{abbr:8}[/cyan] - {name} (ID: {gid})")


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
