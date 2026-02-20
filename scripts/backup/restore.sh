#!/bin/bash
# Restore script for TCG Inventory System
# Usage: ./restore.sh <backup_directory>

set -e  # Exit on error

# Check arguments
if [ -z "$1" ]; then
    echo "Usage: $0 <backup_directory>"
    echo "Example: $0 backups/20240111_020000"
    exit 1
fi

BACKUP_DIR="$1"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warn() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Verify backup directory exists
if [ ! -d "$PROJECT_ROOT/$BACKUP_DIR" ]; then
    log_error "Backup directory not found: $BACKUP_DIR"
    exit 1
fi

echo "🔄 Starting restore from: $BACKUP_DIR"
echo ""

# Show backup manifest
if [ -f "$PROJECT_ROOT/$BACKUP_DIR/MANIFEST.txt" ]; then
    cat "$PROJECT_ROOT/$BACKUP_DIR/MANIFEST.txt"
    echo ""
fi

# Confirmation prompt
read -p "⚠️  This will overwrite current data. Continue? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "Restore cancelled."
    exit 0
fi

# Stop services
echo ""
echo "🛑 Stopping services..."
if command -v docker &> /dev/null && [ -f "$PROJECT_ROOT/docker/docker-compose.yml" ]; then
    cd "$PROJECT_ROOT/docker" && docker compose down || true
    log_info "Docker services stopped"
else
    log_warn "Docker not available or compose file not found"
fi

# Backup current state (just in case)
SAFETY_BACKUP="$PROJECT_ROOT/backups/pre-restore-$(date +%Y%m%d_%H%M%S)"
mkdir -p "$SAFETY_BACKUP"
if [ -f "$PROJECT_ROOT/backend/auth.db" ]; then
    cp "$PROJECT_ROOT/backend/auth.db" "$SAFETY_BACKUP/auth.db"
    log_info "Current state backed up to: $SAFETY_BACKUP"
else
    log_info "No local auth.db to backup (authentication via Odoo)"
fi

# Restore optional auth database (if in backup)
if [ -f "$PROJECT_ROOT/$BACKUP_DIR/auth.db" ]; then
    cp "$PROJECT_ROOT/$BACKUP_DIR/auth.db" "$PROJECT_ROOT/backend/auth.db"
    log_info "Optional local auth database restored (login tracking)"
else
    log_warn "No auth database in backup - system uses Odoo authentication"
fi

# Restore Docker volumes
if command -v docker &> /dev/null; then
    if [ -f "$PROJECT_ROOT/$BACKUP_DIR/redis-data.tar.gz" ]; then
        log_warn "Clearing Redis data before restore..."
        docker run --rm \
            -v tcg-redis-data:/data \
            alpine sh -c "cd /data && rm -rf ./*" 2>/dev/null || log_warn "Redis clear failed"
        docker run --rm \
            -v tcg-redis-data:/data \
            -v "$PROJECT_ROOT/$BACKUP_DIR":/backup \
            alpine sh -c "tar xzf /backup/redis-data.tar.gz -C /data" 2>/dev/null || log_warn "Redis restore failed"
        log_info "Redis data restored"
    fi

    if [ -f "$PROJECT_ROOT/$BACKUP_DIR/meili-data.tar.gz" ]; then
        log_warn "Clearing Meilisearch data before restore..."
        docker run --rm \
            -v tcg-meili-data:/data \
            alpine sh -c "cd /data && rm -rf ./*" 2>/dev/null || log_warn "Meilisearch clear failed"
        docker run --rm \
            -v tcg-meili-data:/data \
            -v "$PROJECT_ROOT/$BACKUP_DIR":/backup \
            alpine sh -c "tar xzf /backup/meili-data.tar.gz -C /data" 2>/dev/null || log_warn "Meilisearch restore failed"
        log_info "Meilisearch data restored"
    fi
fi

# Remind about env file
if [ -f "$PROJECT_ROOT/$BACKUP_DIR/env.template" ]; then
    echo ""
    log_warn "Remember to restore secrets in .env file!"
    log_warn "Template available at: $BACKUP_DIR/env.template"
fi

# Restart services
echo ""
echo "🚀 Restarting services..."
if command -v docker &> /dev/null && [ -f "$PROJECT_ROOT/docker/docker-compose.yml" ]; then
    cd "$PROJECT_ROOT/docker" && docker compose up -d
    log_info "Docker services started"
else
    log_warn "Docker not available. Start services manually."
fi

echo ""
log_info "Restore complete!"
echo ""
echo "Safety backup created at: $SAFETY_BACKUP"
echo "If something went wrong, restore with:"
echo "  ./scripts/backup/restore.sh $(basename $SAFETY_BACKUP)"
