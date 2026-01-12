# Scripts

Utility scripts for managing the TCG Inventory system.

## 📁 Directory Structure

```
scripts/
├── backup/          # Backup and restore operations
├── data/            # Data import and image fixing
├── deploy/          # Deployment automation
├── maintenance/     # Maintenance and sync tasks
└── server/          # Server startup scripts
```

---

## 📊 Data

Scripts for importing card data and fixing images.

| Script | Description |
|--------|-------------|
| `data/import_csv.py` | Import card sets from CSV files into Odoo |
| `data/fix_images.py` | Fix missing images using TCGPlayer CDN |
| `data/fix_images_tcgdex.py` | Fix missing images using TCGDex API |
| `data/cleanup_database.py` | Find and clean duplicate products, empty sets |

**Usage:**
```bash
# Import a card set from CSV
python scripts/data/import_csv.py

# Fix missing images (dry run first)
python scripts/data/fix_images.py --dry-run
python scripts/data/fix_images.py

# Fix images using TCGDex API
python scripts/data/fix_images_tcgdex.py --set SV10

# Clean up database (dry run first)
python scripts/data/cleanup_database.py --dry-run
python scripts/data/cleanup_database.py
```

---

## 🔄 Backup

Scripts for backing up and restoring data.

| Script | Description |
|--------|-------------|
| `backup/backup.sh` | Create backup of database, config, and Docker volumes |
| `backup/restore.sh` | Restore from a backup directory |

**Usage:**
```bash
# Create backup
./scripts/backup/backup.sh

# Create backup to specific directory
./scripts/backup/backup.sh backups/2024-01-15

# Restore from backup
./scripts/backup/restore.sh backups/2024-01-15
```

---

## 🚀 Deploy

Deployment automation scripts.

| Script | Description |
|--------|-------------|
| `deploy/deploy-webhook.py` | Webhook server for auto-deployment from GitHub |
| `deploy/tcg-autodeploy.service` | Systemd service for the webhook server |

**Setup auto-deploy:**
```bash
# Install systemd service
sudo cp scripts/deploy/tcg-autodeploy.service /etc/systemd/system/
sudo systemctl enable tcg-autodeploy
sudo systemctl start tcg-autodeploy
```

---

## 🔧 Maintenance

Maintenance and data sync scripts.

| Script | Description |
|--------|-------------|
| `maintenance/sync-prices.sh` | Sync card prices from external sources |
| `maintenance/sync-prices.bat` | Windows version of price sync |
| `maintenance/setup_warehouses.py` | Initialize Odoo warehouse configuration |

**Usage:**
```bash
# Sync prices (Linux/Mac)
./scripts/maintenance/sync-prices.sh

# Setup warehouses
python scripts/maintenance/setup_warehouses.py
```

---

## 🖥️ Server

Development server startup scripts.

| Script | Description |
|--------|-------------|
| `server/start-server.sh` | Start the FastAPI backend (Linux/Mac) |
| `server/start-server.bat` | Start the FastAPI backend (Windows) |

**Usage:**
```bash
# Start development server
./scripts/server/start-server.sh
```

---

## Notes

- All `.sh` scripts should be run from the project root directory
- Ensure scripts have execute permissions: `chmod +x scripts/**/*.sh`
- Set environment variables in `.env` before running scripts

