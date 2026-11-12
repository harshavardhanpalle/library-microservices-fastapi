# Library Microservices – DevOps Delivery on AWS

Automated build, release and monitoring of three existing microservices (**Users, Books, Orders**; FastAPI + PostgreSQL behind Nginx) using **GitHub → Jenkins → Amazon ECR → AWS EC2 (Docker Compose)**, provisioned with **Terraform** and monitored with **Prometheus + Grafana**.
The application code is unchanged from upstream (see `docs/APP_README.md`); everything else here is DevOps work.

## Architecture

```
Developer ─PR→ GitHub ──webhook/poll──▶ Jenkins (own EC2, port 8080 restricted to your IP)
                                          │ validate → test → build → tag → push
                                          ▼
                                   Amazon ECR (library/users | books | orders)
                                          │ pull via EC2 IAM role
Terraform ─provisions─▶ EC2 (Ubuntu 22.04, Docker Compose)
                          ├─ nginx :80 ─▶ /api/users  /api/books  /api/orders
                          ├─ users / books / orders services ─▶ PostgreSQL (volume)
                          └─ monitoring (127.0.0.1 only): Prometheus, Grafana,
                             node-exporter, cAdvisor, blackbox-exporter
```

| Path | Purpose |
|---|---|
| `Jenkinsfile` | CI/CD pipeline |
| `docker-compose.yml` / `docker-compose.prod.yml` | App stack / ECR images + health checks |
| `docker-compose.monitoring.yml`, `monitoring/` | Prometheus, Grafana, exporters, alert rules, dashboard |
| `terraform/` | EC2, 3×ECR, SG, IAM role, Jenkins push-only IAM user, budget |
| `scripts/` | `deploy.sh` (deploy+verify+auto-rollback), `rollback.sh`, `verify.sh`, `simulate-failure.sh` |
| `nginx/nginx.conf` | Reverse proxy routing |

Image tags: `<jenkins-build-number>-<git-short-sha>` (ECR tags are immutable). No `latest`.

## Prerequisites
AWS account (check Free Tier/pricing), AWS CLI, Terraform ≥ 1.5, Docker, Git, an SSH key pair, Jenkins runs on its own EC2 instance created by Terraform (set `create_jenkins_host = false` to use your workstation instead). Required plugins: Pipeline, Git, GitHub, SSH Agent, Credentials Binding, JUnit; the bootstrap script already installs Docker, Python 3, AWS CLI and Git on the Jenkins host.

## Branch workflow
`main` = released/deployable (protected, PR + passing checks required) · `develop` = integration · `feature/*`, `devops/*` branch from `develop` and merge by PR · release = PR `develop → main`. No secrets in commits (`.gitignore` covers `.env`, `*.pem`, `*.tfstate`, `terraform.tfvars`).

## Deployment steps
1. **Infrastructure**
   ```bash
   cd terraform
   cp terraform.tfvars.example terraform.tfvars   # set ssh_public_key, allowed_ssh_cidrs (your IP + Jenkins IP), budget_email
   terraform init && terraform validate && terraform plan -out=tfplan && terraform apply tfplan
   terraform output
   ```
2. **Open Jenkins** – `terraform output jenkins_url` (wait ~5 min after apply). Unlock with `ssh ubuntu@<jenkins-ip> 'sudo cat /var/lib/jenkins/secrets/initialAdminPassword'`, install suggested plugins plus *SSH Agent*, *Pipeline*, *GitHub*, *Credentials Binding*, *JUnit*.
2b. **Jenkins IAM key** – In the AWS console create an access key for the IAM user in output `jenkins_iam_user` (push-only to the 3 repos). Never commit it.
3. **Jenkins credentials** (Manage Jenkins → Credentials):
   - `aws-jenkins` – Username with password: access key ID / secret access key
   - `ec2-ssh` – SSH private key for user `ubuntu`
   - `ec2-host` – Secret text: the app host IP. With Jenkins on EC2 use the **private** IP (`terraform output app_private_ip`); with Jenkins on a workstation use the public IP
4. **Pipeline job** – New *Pipeline from SCM* → this repo → `Jenkinsfile`. Trigger: GitHub webhook to `http://<jenkins>/github-webhook/` (Jenkins stays private → use a tunnel such as smee.io/ngrok, or rely on the built-in 5-minute SCM polling).
5. **Run** *Build with Parameters* (`AWS_REGION` matching Terraform). Stages: Checkout → Validate config → Test → Build & tag → Push to ECR → Deploy to EC2 → Verify.
6. **Verify** – `curl http://<ec2-ip>/api/users/health` (also `/books`, `/orders`).
7. **Monitoring** – deployed automatically by `deploy.sh`; ports are localhost-only:
   ```bash
   ssh -L 3000:127.0.0.1:3000 -L 9090:127.0.0.1:9090 ubuntu@<ec2-ip>
   # Grafana http://localhost:3000 (admin / password in /opt/library/.env.monitoring), dashboard "Library Microservices Overview"
   ```

Local run without AWS: `cp .env.example .env && docker compose up --build` → `http://localhost:8080/api/users/health`.

## Update demo
Change any file (e.g. a comment or config value) → PR → merge → Jenkins builds a new tag → ECR → EC2 updated, verified.

## Rollback / recovery
- **Automatic:** `deploy.sh` runs `verify.sh`; on failure it redeploys the previous tag (`.current_tag` / `.previous_tag` on the host) and fails the build.
- **Manual (pipeline):** run Jenkins with `DEPLOY_TAG=<older tag>` (skips build/push, deploys that ECR image).
- **Manual (host):** `cd /opt/library && ECR_REGISTRY=<registry> bash scripts/rollback.sh`
- **Data:** PostgreSQL data lives in the `postgres_data` volume and survives redeploys.

## Troubleshooting & incident simulation
See `docs/TROUBLESHOOTING.md`. Quick commands: `docker compose -p library ps`, `docker compose -p library logs -f <svc>`, `journalctl -u docker`, `df -h`, `free -m`, `top`.

## Cleanup
```bash
ssh ubuntu@<ec2-ip> 'cd /opt/library && docker compose -p library-monitoring down -v && docker compose -p library down -v'
cd terraform && terraform destroy        # removes EC2, ECR repos (+images), SG, IAM, budget
```
Then delete the Jenkins IAM access key (the user is removed by `destroy`; remove the key first if destroy complains) and confirm in the AWS console that nothing is left.

## Security notes
IMDSv2 required · encrypted gp3 volume · SSH only from approved CIDRs · only port 80 public · Grafana/Prometheus bound to localhost · EC2 uses an IAM role (no keys on host) · Jenkins user is push-only · containers run as non-root, read-only FS, all capabilities dropped · `.env` generated on the host with a random DB password.
