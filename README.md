# TCG Automation

Pokemon TCG inventory automation for Odoo ERP. Import card sets, sync prices, generate labels, and scan cards into inventory.

## Features

- **Import Sets**: Fetch card data from tcgcsv.com and create products in Odoo
- **Price Sync**: Automatically update prices from TCGPlayer market data
- **Label Generation**: Create printable labels for toploaders
- **Card Scanner**: Web-based interface for scanning cards into inventory

## Quick Start

### Prerequisites

- Python 3.10+
- Odoo 16+ with custom fields configured
- Network access to Odoo instance

### Installation

```bash
# Clone the repository
git clone https://github.com/jleyva816/tcg-automation.git
cd tcg-automation

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: .\venv\Scripts\activate  # Windows

# Install package
pip install -e .

# Configure environment
cp env.example .env
# Edit .env with your Odoo credentials
```

### Configuration

Create a `.env` file with your Odoo credentials:

```env
ODOO_URL=http://192.168.10.105:8069
ODOO_DB=TCG-Cards
ODOO_USER=your-email@example.com
ODOO_PASSWORD=your-password
```

## CLI Commands

### Check Status

```bash
tcg status
```

### List Available Sets

```bash
tcg list-sets
```

### Import a Set

```bash
# Dry run (preview only)
tcg import sv09 --dry-run

# Import with images
tcg import sv09

# Replace existing products
tcg import sv09 --delete-existing

# Skip image downloads
tcg import sv09 --skip-images
```

### Sync Prices

```bash
# Sync all sets
tcg sync

# Sync specific set
tcg sync --set sv09

# Dry run
tcg sync --dry-run
```

### Start Card Scanner Server

```bash
tcg server

# Custom port
tcg server --port 8080

# Production mode
tcg server --no-debug
```

Then open http://localhost:5000 in your browser.

### Generate Labels

```bash
# Single label
tcg labels me02-001

# Multiple labels
tcg labels me02-001 me02-002 me02-003

# All labels for a set
tcg labels --set sv09 -o sv09_labels.pdf
```

## Docker Deployment

### Build and Run

```bash
cd docker

# Build image
docker compose build

# Start scanner server
docker compose up -d tcg-scanner

# View logs
docker compose logs -f tcg-scanner
```

### Run Price Sync

```bash
# One-time sync
docker compose run --rm tcg-price-sync

# Or schedule with cron
0 6 * * * cd /path/to/tcg-automation/docker && docker compose run --rm tcg-price-sync
```

## NixOS Deployment

For NixOS/Proxmox deployment, see the `nix/` directory for flake configuration.

```bash
# Build with Nix
nix build .#tcg-automation

# Run
./result/bin/tcg --help
```

## Project Structure

```
tcg-automation/
├── src/tcg_automation/         # Main Python package
│   ├── __init__.py
│   ├── cli.py                  # CLI entry point
│   ├── config.py               # Configuration management
│   ├── odoo_client.py          # Odoo XML-RPC client
│   ├── commands/
│   │   ├── import_set.py       # Import card sets
│   │   ├── sync_prices.py      # Update prices
│   │   ├── labels.py           # Generate labels
│   │   └── server.py           # Web scanner server
│   └── web/
│       └── scanner.html        # Scanner UI
├── scripts/                    # Utility scripts
│   ├── start-server.bat        # Windows server launcher
│   ├── start-server.sh         # Linux/Mac server launcher
│   ├── sync-prices.bat         # Windows price sync
│   └── sync-prices.sh          # Linux/Mac price sync
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── nix/
│   └── flake.nix
├── .github/workflows/
│   └── ci.yml
├── pyproject.toml              # Package configuration
├── env.example                 # Environment template
└── README.md
```

## Odoo Configuration

The following custom fields are required on `product.product`:

| Field | Type | Description |
|-------|------|-------------|
| `x_sku` | Char | TCGPlayer SKU (indexed) |
| `x_rarity` | Char | Card rarity |
| `x_set_name` | Char | Set name |
| `x_list_on_ebay` | Boolean | eBay listing flag |
| `x_ebay_item_id` | Char | eBay item ID |
| `x_ebay_listing_url` | Char | eBay listing URL |

## Supported Sets

| Code | Name | Group ID |
|------|------|----------|
| SV09 | Journey Together | 23901 |
| ME02 | Phantasmal Flames | 23783 |
| SV08 | Surging Sparks | 23779 |
| SV07 | Stellar Crown | 23654 |
| SV06 | Twilight Masquerade | 23580 |
| SV05 | Temporal Forces | 23457 |
| SV04 | Paradox Rift | 23360 |
| SV03 | Obsidian Flames | 23218 |
| SV02 | Paldea Evolved | 23104 |
| SV01 | Scarlet & Violet | 22926 |

To add more sets, edit `SET_MAPPINGS` in `src/tcg_automation/commands/import_set.py`.

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run linter
ruff check src/

# Run type checker
mypy src/

# Run tests
pytest tests/ -v
```

## Roadmap

- [x] Phase 1: Card import from tcgcsv.com
- [x] Phase 2: Price sync automation
- [x] Phase 2.5: Label generation & scanner
- [ ] Phase 3: eBay auto-listing
- [ ] Phase 4: eBay order import

## License

MIT License - see LICENSE file for details.

## Author

Josh Leyva (joshleyva816@gmail.com)

