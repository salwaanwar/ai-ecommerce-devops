#!/usr/bin/env bash
# Runs all security scans locally and saves reports to security/reports/
set -uo pipefail
cd "$(dirname "$0")/.."

OUT=security/reports
IMAGE="${1:-nexvion-ecommerce:local}"
mkdir -p "$OUT"
FAIL=0

echo "==> 1/4 Secret scan (Gitleaks)"
docker run --rm -v "$PWD:/repo" zricethezav/gitleaks:latest detect \
  --source=/repo --no-git --redact --report-format json \
  --report-path=/repo/$OUT/gitleaks.json || FAIL=1

echo "==> 2/4 Dependency / filesystem scan (Trivy fs)"
docker run --rm -v "$PWD:/repo" -v trivy-cache:/root/.cache/ aquasec/trivy:latest fs \
  --scanners vuln,secret --severity HIGH,CRITICAL --no-progress \
  --format table -o /repo/$OUT/trivy-fs.txt /repo/application

echo "==> 3/4 Config scan: Dockerfile, Kubernetes, Helm, Terraform (Trivy config)"
docker run --rm -v "$PWD:/repo" -v trivy-cache:/root/.cache/ aquasec/trivy:latest config \
  --severity HIGH,CRITICAL --no-progress \
  --format table -o /repo/$OUT/trivy-config.txt /repo

echo "==> 4/4 Container image scan (Trivy image: $IMAGE)"
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock -v trivy-cache:/root/.cache/ \
  -v "$PWD/$OUT:/out" aquasec/trivy:latest image \
  --severity HIGH,CRITICAL --no-progress --format table -o /out/trivy-image.txt "$IMAGE"

echo
echo "Reports saved in $OUT/:"
ls -1 "$OUT"
exit $FAIL
