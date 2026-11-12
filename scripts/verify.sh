#!/usr/bin/env bash
# Verifies Nginx routing and all three service health endpoints. Exit 0 = healthy.
set -uo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && { set -a; . ./.env; set +a; }
PORT="${NGINX_HOST_PORT:-80}"
RETRIES="${VERIFY_RETRIES:-30}"

for svc in users books orders; do
  ok=0
  for i in $(seq 1 "$RETRIES"); do
    if curl -fsS --max-time 5 "http://127.0.0.1:${PORT}/api/${svc}/health" >/dev/null 2>&1; then
      echo "OK   /api/${svc}/health"; ok=1; break
    fi
    sleep 5
  done
  if [ "$ok" -ne 1 ]; then echo "FAIL /api/${svc}/health after ${RETRIES} tries"; exit 1; fi
done
echo "All services healthy."
