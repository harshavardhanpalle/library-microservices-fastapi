# Troubleshooting notes & incident simulation

Run on the EC2 host. Capture screenshots of Grafana before / during / after for your evidence.

## Scenario A – container down
1. Baseline: Grafana "Service availability" = 1 for all three services.
2. Break it: `bash /opt/library/scripts/simulate-failure.sh kill` (stops the orders container).
3. Detect: availability panel drops to 0 for `/api/orders/health`; Prometheus alert `ServiceDown` fires after 1 min (`http://localhost:9090/alerts`); `curl /api/orders/health` returns 502.
4. Diagnose: `docker compose -p library ps` (orders exited) → `docker compose -p library logs --tail=50 orders_service` → `docker inspect` exit code → `journalctl -u docker --since "10 min ago"`.
5. Root cause: container stopped (simulated).
6. Fix: `docker compose -p library up -d orders_service`; confirm `bash scripts/verify.sh`.
7. Prevention: `restart: unless-stopped` recovers crashes (not manual stops); alerting on `probe_success`.

## Scenario B – bad config (502 Bad Gateway)
1. `bash scripts/simulate-failure.sh break` (Nginx upstream port changed to 5999).
2. Nginx logs show connection refused to the upstream: `docker compose -p library logs nginx`.
3. Fix: restore `orders_service:5000` in `/opt/library/nginx/nginx.conf`, `docker compose -p library restart nginx`, re-run verify. (Redeploying from Jenkins also restores the file from Git.)

## Scenario C – failed deployment
Deploy a tag that does not exist (`DEPLOY_TAG=999-bad`). `docker compose pull` fails, pipeline goes red; the running version keeps serving. Fix by redeploying a known-good tag.

## Useful checks
`docker stats --no-stream` · `df -h` · `free -m` · `top` · `ss -tlnp` · `docker network inspect library_app_net`
Container-to-container: `docker compose -p library exec nginx wget -qO- http://users_service:5000/health`

## Write-up template (fill in with your real run)
| Item | Your notes |
|---|---|
| Time / symptom | |
| Detection (alert/dashboard) | |
| Commands used | |
| Root cause | |
| Fix | |
| Prevention | |
