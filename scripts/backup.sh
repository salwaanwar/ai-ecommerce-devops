#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="backups"
STAMP=$(date +%Y%m%d_%H%M%S)
mkdir -p "$BACKUP_DIR"

tar -czf "$BACKUP_DIR/ecommerce_$STAMP.tar.gz" application docker kubernetes helm
echo "Backup created: $BACKUP_DIR/ecommerce_$STAMP.tar.gz"

# keep only the 5 newest backups
ls -1t "$BACKUP_DIR"/*.tar.gz | tail -n +6 | xargs -r rm --
