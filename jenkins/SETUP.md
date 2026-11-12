# Jenkins EC2 setup (manual, one time)

You create **one** EC2 by hand for Jenkins. Everything else (app EC2, ECR repos, security group, IAM role for the app)
is created by Terraform **from the Jenkins pipeline**. Jenkins talks to AWS through an **IAM role** (no access keys).

## 1. Create the IAM role, policy and Terraform state bucket (laptop, admin credentials)
```bash
aws configure                              # an admin IAM user (not root)
bash jenkins/setup-aws-prereqs.sh ap-south-1   # use the SAME region everywhere
```
Creates: S3 bucket `library-tfstate-<account-id>`, policy `jenkins-ci-policy`, role `jenkins-ec2-role`,
instance profile `jenkins-ec2-profile`. Policy source: `jenkins/iam/jenkins-policy.json` (review it).

## 2. Launch the Jenkins EC2 (AWS console)
| Setting | Value |
|---|---|
| Name | `library-jenkins` |
| AMI | Ubuntu Server 22.04 LTS (amd64) |
| Type | `t3.small` (2 GB RAM) or larger; check Free Tier / pricing |
| Key pair | create/select one (this is the key you will also store in Jenkins as `ec2-ssh`) |
| Network | **default VPC** (Terraform deploys the app host in the default VPC) |
| Security group (new) | inbound **22** and **8080** from **My IP only**. Do not open 8080 to the world |
| Storage | 25 GiB gp3 |
| Advanced > IAM instance profile | **`jenkins-ec2-profile`** |
| Advanced > User data | paste the content of `jenkins/bootstrap-jenkins.sh` (or run it later over SSH with sudo) |

Wait ~5 minutes, then `ssh -i <key>.pem ubuntu@<jenkins-public-ip>` and check `cat /var/log/bootstrap-done`.

## 3. Unlock Jenkins
```bash
sudo cat /var/lib/jenkins/secrets/initialAdminPassword
```
Open `http://<jenkins-public-ip>:8080`, install suggested plugins, then add **SSH Agent** (also brings SSH Credentials) and **JUnit** if missing.

## 4. Add the credential (the only one)
Manage Jenkins > Credentials > Global > Add: **SSH Username with private key**
- ID: `ec2-ssh`  Username: `ubuntu`  Private key: paste the full key from your `.pem` (keep the final newline).
- The pipeline derives the public key from it and registers it with Terraform. Nothing else to configure.

Optional: Manage Jenkins > System > Global properties > Environment variables: `ADMIN_CIDR` = `x.x.x.x/32` (your IP) to
allow your laptop to SSH to the app host (monitoring tunnel). Without it only Jenkins can SSH to the app host.

## 5. Create the job
New Item > Pipeline > "Pipeline script from SCM" > Git > your repo URL > branch `*/main` > Script Path `Jenkinsfile`.
Build once (it may fail while it registers the parameters) then use **Build with Parameters**.

## 6. Run
| ACTION | What happens |
|---|---|
| `plan-only` | Validate + `terraform plan` (saves `plan.txt`). Use first. |
| `deploy` | Validate, tests, Terraform apply, build+tag images, push to ECR, deploy to EC2, verify |
| `destroy` | Asks for confirmation, then `terraform destroy` (EC2, ECR repos + images, SG, app IAM role) |

Rollback: run `deploy` with `DEPLOY_TAG=<older tag>`.

## 7. Cleanup (end of project)
1. Run the pipeline with `ACTION=destroy`.
2. Terminate the Jenkins EC2 and delete its security group.
3. `bash jenkins/teardown-aws-prereqs.sh` (removes the role, policy, instance profile and state bucket).
4. Check the console: EC2, EBS volumes, ECR, S3, IAM, Elastic IPs. Remove budget alerts if you no longer need them.
