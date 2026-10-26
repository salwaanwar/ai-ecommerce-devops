#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="docker/docker-compose.yml"
echo "==> Deploying application"
docker compose -f "$COMPOSE_FILE" up -d --build
sleep 3
./scripts/health-check.sh
