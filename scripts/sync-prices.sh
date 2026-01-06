#!/bin/bash
# TCG Price Sync - Linux/Mac Script
# Schedule with cron: 0 6 * * * /path/to/sync-prices.sh
#
# Usage: ./sync-prices.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# Load environment
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Run price sync
tcg sync


