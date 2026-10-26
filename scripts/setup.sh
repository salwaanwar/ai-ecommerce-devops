#!/usr/bin/env bash
set -euo pipefail

echo "==> Checking required tools"
MISSING=0
for tool in git curl docker; do
  if command -v "$tool" >/dev/null 2>&1; then
    echo "  [OK] $tool: $($tool --version | head -n1)"
  else
    echo "  [MISSING] $tool"
    MISSING=1
  fi
done

if [ "$MISSING" = "1" ]; then
  echo "Install missing tools (Ubuntu): sudo apt update && sudo apt install -y git curl docker.io"
  exit 1
fi

mkdir -p logs backups
echo "==> Environment ready"
