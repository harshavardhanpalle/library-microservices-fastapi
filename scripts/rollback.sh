#!/usr/bin/env bash
# Manual rollback on the EC2 host: redeploy the previously recorded good tag.
set -euo pipefail
cd "$(dirname "$0")/.."
PREV="$(cat .previous_tag 2>/dev/null || true)"
[ -n "$PREV" ] || { echo "No .previous_tag recorded"; exit 1; }
: "${ECR_REGISTRY:?ECR_REGISTRY must be set}"
exec bash scripts/deploy.sh "$PREV"
