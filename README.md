# Library Microservices – DevOps Delivery on AWS

Automated build, release and monitoring of three existing microservices (**Users, Books, Orders**; FastAPI + PostgreSQL behind Nginx)
using **GitHub → Jenkins → Terraform → Amazon ECR → AWS EC2 (Docker Compose)**, monitored with **Prometheus + Grafana**.
The application code is unchanged from upstream (see `docs/APP_README.md`); everything else is DevOps work.

## Architecture
```
Developer ─PR→ GitHub ──webhook/poll──▶ Jenkins (manually created EC2, IAM role, UI 8080 restricted to your IP)
                                          │ validate → test → terraform apply → build → tag → push → deploy → verify
                                          ├─ Terraform (state in S3) ─▶ app EC2, 3× ECR, security group, app IAM role
                                          ▼
                                   Amazon ECR (library/users | books | orders)
                                          │ pulled by the app EC2 through its IAM role
                                   App EC2 (Ubuntu 22.04, Docker Compose)
                                     ├─ nginx :80 ─▶ /api/users  /api/books  /api/orders
                                     ├─ users / books / orders services ─▶ PostgreSQL (volume)
                                     └─ monitoring (127.0.0.1 only): Prometheus, Grafana, node-exporter, cAdvisor, blackbox
```
| Path | Purpose |
|---|---|
| `Jenkinsfile` | Full pipeline incl. Terraform (`ACTION` = deploy / plan-only / destroy) |
| `jenkins/` | One-time setup: IAM policy + role scripts, Jenkins bootstrap, `SETUP.md` |
| `terraform/` | App EC2, 3×ECR, security group, app IAM role, optional budget; S3 remote state |
| `docker-compose.yml` / `docker-compose.prod.yml` | App stack / ECR images + health checks |
| `docker-compose.monitoring.yml`, `monitoring/` | Prometheus, Grafana, exporters, alert rules, dashboard |
| `scripts/` | `deploy.sh` (deploy+verify+auto-rollback), `rollback.sh`, `verify.sh`, `simulate-failure.sh` |
| `nginx/nginx.conf` | Reverse proxy routing |

Image tags: `<jenkins-build-number>-<git-short-sha>` (ECR tags are immutable). No `latest`.

## Prerequisites
AWS account (check Free Tier/pricing, set a budget alert), AWS CLI and an admin IAM user for the one-time setup, Git, Docker (for local runs),
an SSH key pair. Terraform and Jenkins run on the Jenkins EC2 (installed by `jenkins/bootstrap-jenkins.sh`).

## Branch workflow
`main` = released/deployable (protected, PR + passing checks required) · `develop` = integration · `feature/*`, `devops/*` branch from `develop`
and merge by PR · release = PR `develop → main`. No secrets in commits (`.gitignore` covers `.env`, `*.pem`, `*.tfstate`, `terraform.tfvars`).

## Deployment steps
1. **One-time AWS prerequisites and Jenkins** – follow `jenkins/SETUP.md` (IAM role/instance profile + state bucket, launch Jenkins EC2, add the `ec2-ssh` credential, create the pipeline job).
2. **Plan** – Build with Parameters: `ACTION=plan-only`. Review `plan.txt` (archived artifact).
3. **Deploy** – `ACTION=deploy`. Stages: Checkout → Prepare AWS context → Validate → Test → Terraform plan & apply → Build & tag → Push to ECR → Deploy to EC2 → Verify.
4. **Verify** – `curl http://<app-ip>/api/users/health` (also `/books`, `/orders`). Jenkins also verifies through the private IP.
5. **Monitoring** – deployed by `deploy.sh`; ports are localhost-only. With `ADMIN_CIDR` set (or hop through Jenkins):
   ```bash
   ssh -L 3000:127.0.0.1:3000 -L 9090:127.0.0.1:9090 ubuntu@<app-ip>
   # Grafana http://localhost:3000 (admin / password in /opt/library/.env.monitoring), dashboard "Library Microservices Overview"
   ```
6. **Trigger** – GitHub webhook to `http://<jenkins>/github-webhook/` (Jenkins stays private, so use a tunnel such as smee.io/ngrok) or rely on the built-in 5-minute SCM polling.

Local run without AWS: `cp .env.example .env && docker compose up --build` → `http://localhost:8080/api/users/health`.

## Update demo
Change any file (e.g. a comment or config value) → PR → merge → Jenkins builds a new tag → ECR → EC2 updated and verified.

## Rollback / recovery
- **Automatic:** `deploy.sh` runs `verify.sh`; on failure it redeploys the previous tag (`.current_tag` / `.previous_tag` on the host) and fails the build.
- **Manual (pipeline):** `ACTION=deploy` with `DEPLOY_TAG=<older tag>` (skips test/build/push, deploys that ECR image).
- **Manual (host):** `cd /opt/library && ECR_REGISTRY=<registry> bash scripts/rollback.sh`
- **Data:** PostgreSQL data lives in the `postgres_data` volume and survives redeploys.

## Troubleshooting & incident simulation
See `docs/TROUBLESHOOTING.md`. Quick commands: `docker compose -p library ps`, `docker compose -p library logs -f <svc>`, `journalctl -u docker`, `df -h`, `free -m`, `top`.

## Cleanup
1. Jenkins: Build with Parameters `ACTION=destroy` (confirm) – removes app EC2, ECR repos (+images), security group, app IAM role.
2. Terminate the Jenkins EC2, then `bash jenkins/teardown-aws-prereqs.sh` (role, policy, instance profile, state bucket).
3. Confirm in the AWS console that no instances, volumes, repositories, buckets or IAM leftovers remain.

## Security notes
No AWS access keys anywhere: Jenkins uses an instance **role**, the app host uses a separate read-only ECR role · Jenkins role is scoped to `library-*` IAM names, `library/*` ECR repos,
the state bucket, and may only attach the ECR read-only managed policy · IMDSv2 required · encrypted gp3 volumes · SSH only from Jenkins' security group and optional admin IP ·
only port 80 public · Jenkins UI limited to your IP · Grafana/Prometheus bound to localhost · Terraform state in a private, encrypted, non-public S3 bucket ·
containers run as non-root, read-only FS, all capabilities dropped · `.env` generated on the host with a random DB password.
