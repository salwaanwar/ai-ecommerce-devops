#!/usr/bin/env bash
set -euo pipefail

echo "==> Removing stopped containers and dangling images"
docker container prune -f
docker image prune -f

echo "==> Deleting logs older than 7 days"
find logs -type f -name "*.log" -mtime +7 -delete 2>/dev/null || true
echo "==> Cleanup done"
