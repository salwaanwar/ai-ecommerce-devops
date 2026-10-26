#!/usr/bin/env bash
set -euo pipefail

URL="${1:-http://localhost:${APP_PORT:-8082}/health}"
RETRIES=5

for i in $(seq 1 $RETRIES); do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" "$URL" || true)
  if [ "$CODE" = "200" ]; then
    echo "[$(date '+%F %T')] HEALTHY ($URL -> 200)"
    exit 0
  fi
  echo "Attempt $i/$RETRIES failed (HTTP $CODE). Retrying..."
  sleep 2
done

echo "[$(date '+%F %T')] UNHEALTHY: $URL"
exit 1
