#!/usr/bin/env bash
# Runs ON the EC2 host. Usage: ECR_REGISTRY=<registry> AWS_REGION=<region> bash scripts/deploy.sh <image-tag>
# Pulls the tag from ECR (via the instance IAM role), starts the stack, verifies, and auto-rolls back on failure.
set -euo pipefail
cd "$(dirname "$0")/.."

TAG="${1:?usage: deploy.sh <image-tag>}"
: "${ECR_REGISTRY:?ECR_REGISTRY must be set}"
AWS_REGION="${AWS_REGION:-us-east-1}"

# First run: create .env with a random DB password (never committed)
if [ ! -f .env ]; then
  sed -e "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$(openssl rand -hex 16)/" \
      -e "s/^NGINX_HOST_PORT=.*/NGINX_HOST_PORT=80/" .env.example > .env
  chmod 600 .env
  echo "Created .env with generated DB password"
fi
if [ ! -f .env.monitoring ]; then
  echo "GRAFANA_ADMIN_PASSWORD=$(openssl rand -hex 12)" > .env.monitoring
  chmod 600 .env.monitoring
fi

APP=(docker compose -p library --env-file .env -f docker-compose.yml -f docker-compose.prod.yml)
MON=(docker compose -p library-monitoring --env-file .env.monitoring -f docker-compose.monitoring.yml)

aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$ECR_REGISTRY"

PREV="$(cat .current_tag 2>/dev/null || true)"
export ECR_REGISTRY

echo "==> Deploying tag: $TAG (previous: ${PREV:-none})"
export IMAGE_TAG="$TAG"
"${APP[@]}" pull
"${APP[@]}" up -d --no-build --remove-orphans

if bash scripts/verify.sh; then
  [ -n "$PREV" ] && [ "$PREV" != "$TAG" ] && echo "$PREV" > .previous_tag
  echo "$TAG" > .current_tag
  "${MON[@]}" up -d
  docker image prune -f >/dev/null
  echo "==> Deploy of $TAG succeeded"
else
  echo "!!! Verification failed. Container status and recent logs:"
  "${APP[@]}" ps || true
  "${APP[@]}" logs --tail=40 || true
  if [ -n "$PREV" ] && [ "$PREV" != "$TAG" ]; then
    echo "==> Rolling back to $PREV"
    export IMAGE_TAG="$PREV"
    "${APP[@]}" pull
    "${APP[@]}" up -d --no-build --remove-orphans
    bash scripts/verify.sh && echo "==> Rollback to $PREV OK" || echo "!!! Rollback also unhealthy"
  else
    echo "No previous tag to roll back to."
  fi
  exit 1
fi
