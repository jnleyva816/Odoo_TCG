"""
Download card set data from tcgcsv.com and organize by set/date.

This creates a historical record of pricing data:
    csvs/
      sv09/
        2026-01-16_ProductsAndPrices.csv
        2026-01-17_ProductsAndPrices.csv
      sv08/
        ...

API: https://tcgcsv.com/tcgplayer/{categoryId}/{groupId}/ProductsAndPrices.csv
"""

from datetime import datetime
from pathlib import Path

import requests
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

console = Console()

# Session for faster HTTP requests
session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 TCG-Importer/1.0"})

# Pokemon category ID on TCGPlayer
POKEMON_CATEGORY_ID = 3

# Base directory for CSVs (relative to project root)
CSV_BASE_DIR = Path(__file__).parent.parent.parent.parent / "csvs"

# Common set code aliases (maps user-friendly codes to TCGPlayer group IDs)
SET_CODE_ALIASES = {
    # ============================================================
    # SCARLET & VIOLET ERA - Main Sets
    # ============================================================
    "sv10": 24269,  # SV10: Destined Rivals
    "dri": 24269,  # SV10: Destined Rivals (official abbr)
    "sv09": 24073,  # SV09: Journey Together
    "jtg": 24073,  # SV09: Journey Together (official abbr)
    "sv08": 23651,  # SV08: Surging Sparks
    "ssp": 23651,  # SV08: Surging Sparks (official abbr)
    "sv07": 23537,  # SV07: Stellar Crown
    "scr": 23537,  # SV07: Stellar Crown (official abbr)
    "sv06": 23473,  # SV06: Twilight Masquerade
    "twm": 23473,  # SV06: Twilight Masquerade (official abbr)
    "sv05": 23381,  # SV05: Temporal Forces
    "tef": 23381,  # SV05: Temporal Forces (official abbr)
    "sv04": 23286,  # SV04: Paradox Rift
    "par": 23286,  # SV04: Paradox Rift (official abbr)
    "sv03": 23228,  # SV03: Obsidian Flames
    "obf": 23228,  # SV03: Obsidian Flames (official abbr)
    "sv02": 23120,  # SV02: Paldea Evolved
    "pal": 23120,  # SV02: Paldea Evolved (official abbr)
    "sv01": 22873,  # SV01: Scarlet & Violet Base Set
    "svi": 22873,  # SV01: Scarlet & Violet Base Set (official abbr)
    # ============================================================
    # SCARLET & VIOLET ERA - Special Sets
    # ============================================================
    "pre": 23821,  # SV: Prismatic Evolutions
    "sfa": 23529,  # SV: Shrouded Fable
    "paf": 23353,  # SV: Paldean Fates
    "mew": 23237,  # SV: Scarlet & Violet 151
    "svp": 22872,  # SV: Scarlet & Violet Promo Cards
    "sve": 24382,  # SVE: Scarlet & Violet Energies
    # Japanese exclusive SV sets
    "wht": 24326,  # SV: White Flare (Japan)
    "blk": 24325,  # SV: Black Bolt (Japan)
    # ============================================================
    # MEGA EVOLUTION ERA
    # ============================================================
    "me03": 24587,  # ME03: Perfect Order
    "me02": 24448,  # ME02: Phantasmal Flames
    "pfl": 24448,  # ME02: Phantasmal Flames (official abbr)
    "me01": 24380,  # ME01: Mega Evolution
    "meg": 24380,  # ME01: Mega Evolution (official abbr)
    "asc": 24541,  # ME: Ascended Heroes
    "mep": 24451,  # ME: Mega Evolution Promo
    "mee": 24461,  # MEE: Mega Evolution Energies
}

# Set code to SKU prefix mapping (for existing products)
# Maps download set code to the SKU prefix used in Odoo
SKU_PREFIXES = {
    # If your existing products use a different SKU prefix, map it here
    "pre": "svpe",  # Prismatic Evolutions: svpe-001, svpe-002, etc.
    "sfa": "svsf",  # Shrouded Fable
    "paf": "svpf",  # Paldean Fates
    "mew": "sv151",  # Scarlet & Violet 151
    "svp": "svp",  # SV Promo Cards
    "sve": "sve",  # SV Energies
    # Main sets use their set code directly
    "sv01": "sv01",
    "sv02": "sv02",
    "sv03": "sv03",
    "sv04": "sv04",
    "sv05": "sv05",
    "sv06": "sv06",
    "sv07": "sv07",
    "sv08": "sv08",
    "sv09": "sv09",
    "sv10": "sv10",
    # Mega Evolution
    "me01": "me01",
    "me02": "me02",
    "me03": "me03",
    "asc": "mea",
    "mep": "mep",
    "mee": "mee",
}

# Set code to full name mapping (avoids API call during import)
# Format: "CODE: Full Name" to match Odoo category naming convention
SET_NAMES = {
    # Scarlet & Violet Main Sets
    "sv10": "SV10: Destined Rivals",
    "dri": "SV10: Destined Rivals",
    "sv09": "SV09: Journey Together",
    "jtg": "SV09: Journey Together",
    "sv08": "SV08: Surging Sparks",
    "ssp": "SV08: Surging Sparks",
    "sv07": "SV07: Stellar Crown",
    "scr": "SV07: Stellar Crown",
    "sv06": "SV06: Twilight Masquerade",
    "twm": "SV06: Twilight Masquerade",
    "sv05": "SV05: Temporal Forces",
    "tef": "SV05: Temporal Forces",
    "sv04": "SV04: Paradox Rift",
    "par": "SV04: Paradox Rift",
    "sv03": "SV03: Obsidian Flames",
    "obf": "SV03: Obsidian Flames",
    "sv02": "SV02: Paldea Evolved",
    "pal": "SV02: Paldea Evolved",
    "sv01": "SV01: Scarlet & Violet",
    "svi": "SV01: Scarlet & Violet",
    # Scarlet & Violet Special Sets
    "pre": "SVPE: Prismatic Evolutions",
    "sfa": "SVSF: Shrouded Fable",
    "paf": "SVPF: Paldean Fates",
    "mew": "SV151: Scarlet & Violet 151",
    "svp": "SVP: SV Promo Cards",
    "sve": "SVE: SV Energies",
    "wht": "SVWF: White Flare",
    "blk": "SVBB: Black Bolt",
    # Mega Evolution Era
    "me03": "ME03: Perfect Order",
    "me02": "ME02: Phantasmal Flames",
    "pfl": "ME02: Phantasmal Flames",
    "me01": "ME01: Mega Evolution",
    "meg": "ME01: Mega Evolution",
    "asc": "MEA: Ascended Heroes",
    "mep": "MEP: Mega Evolution Promo",
    "mee": "MEE: Mega Evolution Energies",
}


def get_all_pokemon_sets() -> list[dict]:
    """
    Fetch all Pokemon sets from tcgcsv.com.

    Returns:
        List of set dicts with groupId, name, abbreviation
    """
    url = f"https://tcgcsv.com/tcgplayer/{POKEMON_CATEGORY_ID}/groups"
    console.print("[blue]Fetching Pokemon sets from tcgcsv.com...[/blue]")

    resp = session.get(url, timeout=30)
    resp.raise_for_status()

    data = resp.json()
    sets = data.get("results", [])

    console.print(f"[green]Found {len(sets)} Pokemon sets[/green]")
    return sets


def download_set_csv(group_id: int, set_code: str) -> Path | None:
    """
    Download ProductsAndPrices.csv for a set and save to organized folder.

    Args:
        group_id: TCGPlayer group ID
        set_code: Set code for folder name (e.g., 'sv09')

    Returns:
        Path to saved CSV file, or None on error
    """
    url = f"https://tcgcsv.com/tcgplayer/{POKEMON_CATEGORY_ID}/{group_id}/ProductsAndPrices.csv"

    try:
        resp = session.get(url, timeout=60)
        resp.raise_for_status()
    except requests.RequestException as e:
        console.print(f"[red]Failed to download {set_code}: {e}[/red]")
        return None

    # Create directory structure: csvs/{set_code}/
    set_dir = CSV_BASE_DIR / set_code.lower()
    set_dir.mkdir(parents=True, exist_ok=True)

    # Save with date: 2026-01-16_ProductsAndPrices.csv
    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"{today}_ProductsAndPrices.csv"
    filepath = set_dir / filename

    # Write CSV
    filepath.write_text(resp.text, encoding="utf-8")

    # Count rows (excluding header)
    row_count = len(resp.text.strip().split("\n")) - 1

    return filepath, row_count


def get_latest_csv(set_code: str) -> Path | None:
    """
    Get the most recent CSV file for a set.

    Args:
        set_code: Set code (e.g., 'sv09')

    Returns:
        Path to latest CSV, or None if not found
    """
    set_dir = CSV_BASE_DIR / set_code.lower()
    if not set_dir.exists():
        return None

    csv_files = sorted(set_dir.glob("*_ProductsAndPrices.csv"), reverse=True)
    return csv_files[0] if csv_files else None


def download_sets(
    set_codes: list[str] | None = None,
    download_all: bool = False,
) -> dict:
    """
    Download CSVs for specified sets or all sets.

    Args:
        set_codes: List of set codes to download (e.g., ['sv09', 'sv08'])
        download_all: If True, download all Pokemon sets

    Returns:
        Summary dict with success/failure counts
    """
    # Get all available sets from API
    all_sets = get_all_pokemon_sets()

    # Build lookup by abbreviation and groupId
    sets_by_code = {}
    sets_by_id = {}
    for s in all_sets:
        abbr = s.get("abbreviation", "").lower()
        if abbr:
            sets_by_code[abbr] = s
        sets_by_id[s["groupId"]] = s

    # Determine which sets to download
    if download_all:
        # Download all sets that have an abbreviation
        to_download = [
            (s.get("abbreviation", "").lower() or str(s["groupId"]), s)
            for s in all_sets
            if s.get("abbreviation")
        ]
        console.print(f"[blue]Downloading {len(to_download)} sets...[/blue]")
    elif set_codes:
        to_download = []
        for code in set_codes:
            code_lower = code.lower()
            # Check aliases first (sv09 -> group_id)
            if code_lower in SET_CODE_ALIASES:
                group_id = SET_CODE_ALIASES[code_lower]
                if group_id in sets_by_id:
                    s = sets_by_id[group_id]
                    to_download.append((code_lower, s))  # Use the alias as folder name
                else:
                    console.print(f"[yellow]Set {code} not found in API (ID: {group_id})[/yellow]")
            # Check official abbreviations
            elif code_lower in sets_by_code:
                s = sets_by_code[code_lower]
                to_download.append((code_lower, s))
            else:
                console.print(f"[yellow]Unknown set code: {code}[/yellow]")
                console.print("[dim]Try: sv09, sv08, me02, or use 'tcg list-sets' to see all[/dim]")
        if not to_download:
            return {"error": "No valid set codes provided"}
    else:
        return {"error": "No sets specified. Use --all or provide set codes."}

    # Download each set
    stats = {"downloaded": 0, "failed": 0, "total_rows": 0}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Downloading...", total=len(to_download))

        for set_code, set_info in to_download:
            group_id = set_info["groupId"]
            set_name = set_info["name"]

            progress.update(task, description=f"Downloading {set_name}...")

            result = download_set_csv(group_id, set_code)
            if result:
                filepath, row_count = result
                stats["downloaded"] += 1
                stats["total_rows"] += row_count
                console.print(
                    f"  [green]✓[/green] {set_code.upper()}: {set_name} ({row_count} rows)"
                )
            else:
                stats["failed"] += 1

            progress.update(task, advance=1)

    # Summary
    console.print("\n[bold green]Download complete![/bold green]")
    console.print(f"  Downloaded: {stats['downloaded']} sets")
    console.print(f"  Failed: {stats['failed']} sets")
    console.print(f"  Total rows: {stats['total_rows']}")
    console.print(f"  Saved to: {CSV_BASE_DIR}/")

    return stats


def list_downloaded_sets() -> list[dict]:
    """
    List all downloaded sets and their CSV history.

    Returns:
        List of dicts with set info and CSV files
    """
    if not CSV_BASE_DIR.exists():
        return []

    result = []
    for set_dir in sorted(CSV_BASE_DIR.iterdir()):
        if set_dir.is_dir():
            csv_files = sorted(set_dir.glob("*_ProductsAndPrices.csv"), reverse=True)
            if csv_files:
                result.append(
                    {
                        "set_code": set_dir.name,
                        "latest": csv_files[0].name,
                        "count": len(csv_files),
                        "files": [f.name for f in csv_files],
                    }
                )

    return result
