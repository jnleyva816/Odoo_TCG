"""
Barcode generation and management for TCG products.

Generates EAN-13 barcodes using the internal-use prefix (200-299).
Format: 200 + 9-digit sequence + check digit = 13 digits total
"""

import logging
from typing import Any

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from ..odoo_client import get_odoo_client

logger = logging.getLogger(__name__)
console = Console()

# EAN-13 internal use prefix (200-299 reserved for in-store use)
BARCODE_PREFIX = "200"


def calculate_ean13_check_digit(first_12: str) -> str:
    """
    Calculate the EAN-13 check digit.
    
    Algorithm:
    1. Sum digits in odd positions (1, 3, 5, ...) 
    2. Sum digits in even positions (2, 4, 6, ...) and multiply by 3
    3. Add the two sums
    4. Check digit = (10 - (sum % 10)) % 10
    """
    if len(first_12) != 12 or not first_12.isdigit():
        raise ValueError(f"Need exactly 12 digits, got: {first_12}")
    
    odd_sum = sum(int(first_12[i]) for i in range(0, 12, 2))
    even_sum = sum(int(first_12[i]) for i in range(1, 12, 2))
    
    total = odd_sum + (even_sum * 3)
    check_digit = (10 - (total % 10)) % 10
    
    return str(check_digit)


def generate_ean13(sequence_number: int) -> str:
    """
    Generate a valid EAN-13 barcode from a sequence number.
    
    Format: 200 + 9-digit padded sequence + check digit
    
    Args:
        sequence_number: A positive integer (1 to 999,999,999)
    
    Returns:
        13-digit EAN-13 barcode string
    """
    if sequence_number < 1 or sequence_number > 999_999_999:
        raise ValueError(f"Sequence must be 1-999999999, got: {sequence_number}")
    
    # Pad sequence to 9 digits
    sequence_str = str(sequence_number).zfill(9)
    
    # Build first 12 digits: prefix (3) + sequence (9)
    first_12 = f"{BARCODE_PREFIX}{sequence_str}"
    
    # Calculate and append check digit
    check_digit = calculate_ean13_check_digit(first_12)
    
    return f"{first_12}{check_digit}"


def get_next_sequence(odoo) -> int:
    """
    Get the next available barcode sequence number.
    
    Scans existing barcodes in Odoo to find the highest used sequence,
    then returns the next number.
    """
    # Find all products with barcodes starting with our prefix
    products = odoo.search_read(
        "product.product",
        [("barcode", "like", f"{BARCODE_PREFIX}%")],
        ["barcode"],
    )
    
    if not products:
        return 1
    
    max_seq = 0
    for p in products:
        barcode = p.get("barcode", "")
        if barcode and len(barcode) == 13 and barcode.startswith(BARCODE_PREFIX):
            try:
                # Extract sequence (digits 4-12, excluding check digit)
                seq = int(barcode[3:12])
                max_seq = max(max_seq, seq)
            except ValueError:
                continue
    
    return max_seq + 1


def backfill_barcodes(
    dry_run: bool = False,
    set_code: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """
    Add EAN-13 barcodes to existing products that don't have them.
    
    Args:
        dry_run: If True, show what would be done without making changes
        set_code: If provided, only process products from this set
        force: If True, regenerate barcodes even for products that have them
    
    Returns:
        Summary of results
    """
    odoo = get_odoo_client()
    if not odoo.connect():
        return {"error": "Failed to connect to Odoo"}
    
    # Build domain filter
    domain = [("default_code", "!=", False)]  # Has SKU
    
    if set_code:
        domain.append(("default_code", "like", f"{set_code.lower()}-"))
    
    if not force:
        # Only products without barcodes
        domain.append("|")
        domain.append(("barcode", "=", False))
        domain.append(("barcode", "=", ""))
    
    # Get products
    products = odoo.search_read(
        "product.product",
        domain,
        ["id", "name", "default_code", "barcode"],
    )
    
    if not products:
        console.print("[yellow]No products found needing barcodes[/yellow]")
        return {"updated": 0, "skipped": 0}
    
    console.print(f"[green]Found {len(products)} products to update[/green]")
    
    if dry_run:
        console.print("[yellow]DRY RUN - no changes will be made[/yellow]")
    
    # Get starting sequence
    next_seq = get_next_sequence(odoo)
    console.print(f"[blue]Starting barcode sequence: {next_seq}[/blue]")
    
    stats = {"updated": 0, "skipped": 0, "errors": 0}
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        task = progress.add_task("Generating barcodes...", total=len(products))
        
        for product in products:
            progress.update(task, advance=1)
            
            product_id = product["id"]
            sku = product.get("default_code", "")
            current_barcode = product.get("barcode", "")
            
            # Skip if has barcode and not forcing
            if current_barcode and not force:
                stats["skipped"] += 1
                continue
            
            # Generate new barcode
            new_barcode = generate_ean13(next_seq)
            next_seq += 1
            
            if dry_run:
                console.print(f"  [dim]{sku}: would set barcode {new_barcode}[/dim]")
                stats["updated"] += 1
                continue
            
            # Update product
            try:
                odoo.write("product.product", [product_id], {"barcode": new_barcode})
                stats["updated"] += 1
            except Exception as e:
                logger.error(f"Failed to update {sku}: {e}")
                stats["errors"] += 1
    
    console.print(f"\n[bold green]Barcode generation complete![/bold green]")
    console.print(f"  Updated: {stats['updated']}")
    console.print(f"  Skipped: {stats['skipped']}")
    if stats["errors"]:
        console.print(f"  [red]Errors: {stats['errors']}[/red]")
    
    return stats


def verify_barcodes(set_code: str | None = None) -> dict[str, Any]:
    """
    Verify barcode coverage and validity for products.
    
    Args:
        set_code: If provided, only check products from this set
    
    Returns:
        Summary of barcode status
    """
    odoo = get_odoo_client()
    if not odoo.connect():
        return {"error": "Failed to connect to Odoo"}
    
    # Build domain
    domain = [("default_code", "!=", False)]
    if set_code:
        domain.append(("default_code", "like", f"{set_code.lower()}-"))
    
    products = odoo.search_read(
        "product.product",
        domain,
        ["id", "name", "default_code", "barcode"],
    )
    
    stats = {
        "total": len(products),
        "with_barcode": 0,
        "without_barcode": 0,
        "invalid_barcode": 0,
        "valid_ean13": 0,
    }
    
    missing = []
    invalid = []
    
    for p in products:
        barcode = p.get("barcode", "")
        sku = p.get("default_code", "")
        
        if not barcode:
            stats["without_barcode"] += 1
            missing.append(sku)
        else:
            stats["with_barcode"] += 1
            
            # Validate EAN-13
            if len(barcode) == 13 and barcode.isdigit():
                expected_check = calculate_ean13_check_digit(barcode[:12])
                if barcode[12] == expected_check:
                    stats["valid_ean13"] += 1
                else:
                    stats["invalid_barcode"] += 1
                    invalid.append((sku, barcode))
            else:
                stats["invalid_barcode"] += 1
                invalid.append((sku, barcode))
    
    # Display results
    console.print(f"\n[bold]Barcode Verification Report[/bold]")
    if set_code:
        console.print(f"Set: {set_code.upper()}\n")
    
    console.print(f"Total products: {stats['total']}")
    console.print(f"  With barcode: [green]{stats['with_barcode']}[/green]")
    console.print(f"    Valid EAN-13: [green]{stats['valid_ean13']}[/green]")
    if stats["invalid_barcode"]:
        console.print(f"    Invalid format: [yellow]{stats['invalid_barcode']}[/yellow]")
    console.print(f"  Without barcode: [red]{stats['without_barcode']}[/red]")
    
    if missing and len(missing) <= 10:
        console.print(f"\n[yellow]Missing barcodes:[/yellow]")
        for sku in missing[:10]:
            console.print(f"  - {sku}")
        if len(missing) > 10:
            console.print(f"  ... and {len(missing) - 10} more")
    
    return stats

