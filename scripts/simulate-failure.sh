#!/usr/bin/env bash
# Run ON the EC2 host to simulate a container failure for the troubleshooting exercise.
set -euo pipefail
case "${1:-}" in
  kill)    docker stop library-orders_service-1 ;;                       # service down
  oom)     docker kill -s SIGKILL library-books_service-1 ;;             # crash; restart policy should recover it
  break)   cd /opt/library && sed -i 's/orders_service:5000/orders_service:5999/' nginx/nginx.conf \
             && docker compose -p library restart nginx ;;               # 502 from Nginx (wrong upstream port)
  *) echo "usage: $0 {kill|oom|break}"; exit 1 ;;
esac
