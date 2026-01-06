#!/bin/bash
# TCG Card Scanner Server - Linux/Mac
#
# Usage: ./start-server.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# Load environment
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

echo "Starting TCG Card Scanner..."
echo "Open http://localhost:5000 in your browser"
echo

tcg server


