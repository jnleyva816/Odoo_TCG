#!/usr/bin/env python3
"""
Download set logos from TCGdex and save them locally.

This script fetches all Pokemon TCG set logos from TCGdex API,
downloads the images, and creates a mapping file for the backend.

Usage:
    python scripts/download_set_logos.py
"""

import json
from pathlib import Path

import requests

# TCGdex API
TCGDEX_API = "https://api.tcgdex.net/v2/en"

# Output paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
LOGOS_DIR = PROJECT_ROOT / "backend" / "app" / "static" / "logos"
MAPPING_FILE = PROJECT_ROOT / "backend" / "app" / "data" / "set_logos.json"


def fetch_sets() -> list[dict]:
    """Fetch all sets from TCGdex API."""
    print("Fetching sets from TCGdex...")
    resp = requests.get(f"{TCGDEX_API}/sets", timeout=30)
    resp.raise_for_status()
    sets = resp.json()
    print(f"Found {len(sets)} sets")
    return sets


def download_logo(logo_url: str, output_path: Path) -> bool:
    """Download a logo image."""
    try:
        # TCGdex logos are PNG
        full_url = f"{logo_url}.png"
        resp = requests.get(full_url, timeout=10)
        resp.raise_for_status()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(resp.content)
        return True
    except Exception as e:
        print(f"  Failed to download {logo_url}: {e}")
        return False


def main():
    # Fetch all sets
    sets = fetch_sets()

    # Create logos directory
    LOGOS_DIR.mkdir(parents=True, exist_ok=True)

    # Build mapping and download logos
    mapping: dict[str, str] = {}
    downloaded = 0
    skipped = 0

    for s in sets:
        set_id = s.get("id", "")
        set_name = s.get("name", "")
        logo_url = s.get("logo")

        if not set_name or not logo_url:
            continue

        # Normalize name for matching
        name_lower = set_name.lower()

        # Output filename
        safe_id = set_id.replace("/", "-")
        logo_path = LOGOS_DIR / f"{safe_id}.png"

        # Check if already downloaded
        if logo_path.exists():
            skipped += 1
        else:
            print(f"Downloading: {set_name}...")
            if download_logo(logo_url, logo_path):
                downloaded += 1
            else:
                continue

        # Add to mapping (use relative path from static dir)
        mapping[name_lower] = f"/static/logos/{safe_id}.png"

        # Also add set_id as key for code-based lookups
        mapping[set_id.lower()] = f"/static/logos/{safe_id}.png"

    # Save mapping file
    MAPPING_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(MAPPING_FILE, "w") as f:
        json.dump(mapping, f, indent=2, sort_keys=True)

    print("\nDone!")
    print(f"  Downloaded: {downloaded}")
    print(f"  Skipped (existing): {skipped}")
    print(f"  Total mappings: {len(mapping)}")
    print(f"  Mapping file: {MAPPING_FILE}")
    print(f"  Logos directory: {LOGOS_DIR}")


if __name__ == "__main__":
    main()
