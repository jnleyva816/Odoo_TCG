#!/bin/bash
# Backup script for TCG Inventory System
# Usage: ./backup.sh [backup_dir]

set -e  # Exit on error

# Configuration
BACKUP_DIR="${1:-backups/$(date +%Y%m%d_%H%M%S)}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warn() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Create backup directory
mkdir -p "$PROJECT_ROOT/$BACKUP_DIR"

echo "🔄 Starting backup to: $BACKUP_DIR"

# 1. Backup optional local auth database (if exists)
if [ -f "$PROJECT_ROOT/backend/auth.db" ]; then
    cp "$PROJECT_ROOT/backend/auth.db" "$PROJECT_ROOT/$BACKUP_DIR/auth.db"
    log_info "Optional local auth database backed up (login tracking)"
else
    log_warn "No local auth.db found - authentication via Odoo (this is normal)"
fi

# 2. Backup environment template (without secrets)
if [ -f "$PROJECT_ROOT/.env" ]; then
    grep -vE "PASSWORD|SECRET|KEY|TOKEN|API.*KEY" "$PROJECT_ROOT/.env" > "$PROJECT_ROOT/$BACKUP_DIR/env.template" || true
    log_info "Config template backed up (secrets excluded)"
else
    log_warn ".env file not found"
fi

# 3. Backup Docker volumes (if Docker is available)
if command -v docker &> /dev/null; then
    # Check if volumes exist
    if docker volume ls | grep -q "tcg-redis-data"; then
        docker run --rm \
            -v tcg-redis-data:/data \
            -v "$PROJECT_ROOT/$BACKUP_DIR":/backup \
            alpine tar czf /backup/redis-data.tar.gz -C /data . 2>/dev/null || log_warn "Redis data backup failed"
        log_info "Redis data backed up"
    fi
    
    if docker volume ls | grep -q "tcg-meili-data"; then
        docker run --rm \
            -v tcg-meili-data:/data \
            -v "$PROJECT_ROOT/$BACKUP_DIR":/backup \
            alpine tar czf /backup/meili-data.tar.gz -C /data . 2>/dev/null || log_warn "Meilisearch data backup failed"
        log_info "Meilisearch data backed up"
    fi
else
    log_warn "Docker not available, skipping volume backups"
fi

# 4. Create backup manifest
cat > "$PROJECT_ROOT/$BACKUP_DIR/MANIFEST.txt" << EOF
TCG Inventory System Backup
===========================
Created: $(date)
System Version: 2.0.0
Hostname: $(hostname)

Files:
- Optional Local Auth DB: $([ -f "$PROJECT_ROOT/$BACKUP_DIR/auth.db" ] && echo "✓" || echo "✗ (auth via Odoo)")
- Config Template: $([ -f "$PROJECT_ROOT/$BACKUP_DIR/env.template" ] && echo "✓" || echo "✗")
- Redis Data: $([ -f "$PROJECT_ROOT/$BACKUP_DIR/redis-data.tar.gz" ] && echo "✓" || echo "✗")
- Meilisearch Data: $([ -f "$PROJECT_ROOT/$BACKUP_DIR/meili-data.tar.gz" ] && echo "✓" || echo "✗")

Notes:
- PRIMARY DATA: Odoo database must be backed up separately using Odoo's tools
- Local auth.db (if present) only contains login tracking, not user accounts
- User authentication is handled by Odoo, not local database
- Secrets (.env passwords/keys) are NOT backed up for security
- Restore instructions: See docs/BACKUP.md
EOF

# 5. Calculate backup size
BACKUP_SIZE=$(du -sh "$PROJECT_ROOT/$BACKUP_DIR" | cut -f1)

log_info "Backup complete: $BACKUP_DIR (Size: $BACKUP_SIZE)"
echo ""
echo "Backup Contents:"
ls -lh "$PROJECT_ROOT/$BACKUP_DIR"
echo ""
echo "To restore this backup:"
echo "  ./scripts/backup/restore.sh $BACKUP_DIR"
