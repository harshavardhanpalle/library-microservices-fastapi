// End-to-end pipeline: validate -> test -> Terraform (infra) -> build -> push to ECR -> deploy to EC2 -> verify.
// Runs on the manually created Jenkins EC2. AWS access comes from that instance's IAM ROLE (no access keys).
// The only Jenkins credential needed is 'ec2-ssh' (SSH private key, user "ubuntu").
pipeline {
  agent any

  options {
    timestamps()
    disableConcurrentBuilds()
    buildDiscarder(logRotator(numToKeepStr: '20'))
    timeout(time: 60, unit: 'MINUTES')
  }

  // Webhook trigger (needs Jenkins reachable by GitHub) + polling as a fallback
  triggers {
    githubPush()
    pollSCM('H/5 * * * *')
  }

  parameters {
    choice(name: 'ACTION', choices: ['deploy', 'plan-only', 'destroy'], description: 'deploy = infra + build + push + deploy | plan-only = terraform plan only | destroy = remove ALL Terraform-managed infrastructure')
    string(name: 'AWS_REGION', defaultValue: 'ap-south-1', description: 'AWS region (must match the region used when running jenkins/setup-aws-prereqs.sh)')
    string(name: 'DEPLOY_TAG', defaultValue: '', description: 'Optional: deploy an EXISTING image tag from ECR (skips test/build/push). Use for rollback.')
  }

  environment {
    EC2_USER           = 'ubuntu'
    SERVICES           = 'users books orders'
    AWS_DEFAULT_REGION = "${params.AWS_REGION}"
    TF_IN_AUTOMATION   = '1'
    // Optional: define ADMIN_CIDR (your public IP as x.x.x.x/32) under Manage Jenkins > System > Global properties
    // > Environment variables to allow your laptop to SSH to the app host (monitoring tunnel).
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm
        script {
          env.GIT_SHORT = sh(returnStdout: true, script: 'git rev-parse --short HEAD').trim()
          env.IMAGE_TAG = params.DEPLOY_TAG ?: "${env.BUILD_NUMBER}-${env.GIT_SHORT}"
          echo "Action: ${params.ACTION} | Image tag for this run: ${env.IMAGE_TAG}"
        }
      }
    }

    stage('Prepare AWS context') {
      steps {
        script {
          env.ACCOUNT_ID = sh(returnStdout: true, script: 'aws sts get-caller-identity --query Account --output text').trim()
          env.REGISTRY = "${env.ACCOUNT_ID}.dkr.ecr.${params.AWS_REGION}.amazonaws.com"
          env.TF_STATE_BUCKET = "library-tfstate-${env.ACCOUNT_ID}"
          // Security group of THIS Jenkins instance, read from instance metadata (IMDSv2)
          env.JENKINS_SG_ID = sh(returnStdout: true, script: '''
            TOKEN=$(curl -fsS -X PUT http://169.254.169.254/latest/api/token -H "X-aws-ec2-metadata-token-ttl-seconds: 60")
            MAC=$(curl -fsS -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/mac)
            curl -fsS -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/network/interfaces/macs/$MAC/security-group-ids | head -1
          ''').trim()
          def admin = (env.ADMIN_CIDR ?: '').trim()
          env.ADMIN_CIDRS_JSON = admin ? "[\"${admin}\"]" : '[]'
          echo "Account ${env.ACCOUNT_ID} | registry ${env.REGISTRY} | state bucket ${env.TF_STATE_BUCKET} | Jenkins SG ${env.JENKINS_SG_ID} | admin CIDRs ${env.ADMIN_CIDRS_JSON}"
        }
      }
    }

    stage('Validate configuration') {
      steps {
        sh '''
          set -e
          cp .env.example .env
          echo "GRAFANA_ADMIN_PASSWORD=ci" > .env.monitoring.ci
          export ECR_REGISTRY=000000000000.dkr.ecr.us-east-1.amazonaws.com IMAGE_TAG=ci
          docker compose -f docker-compose.yml -f docker-compose.prod.yml config -q
          docker compose --env-file .env.monitoring.ci -f docker-compose.monitoring.yml config -q
          docker run --rm --entrypoint promtool -v "$PWD/monitoring:/etc/prometheus:ro" prom/prometheus:v2.53.0 check config /etc/prometheus/prometheus.yml
          for f in scripts/*.sh jenkins/*.sh terraform/*.sh; do bash -n "$f"; done
          rm -f .env .env.monitoring.ci
          (cd terraform && (terraform fmt -check -recursive || echo "WARNING: terraform fmt reports formatting differences") && terraform init -backend=false -input=false && terraform validate)
        '''
      }
    }

    stage('Test') {
      when { expression { params.ACTION == 'deploy' && !params.DEPLOY_TAG } }
      steps {
        sh '''
          set -e
          python3 -m venv .venv
          . .venv/bin/activate
          pip install -q --upgrade pip
          pip install -q ruff pytest pytest-cov pyyaml httpx
          for s in users books orders; do pip install -q -r ${s}_service/requirements.txt; done
          ruff check .
          pytest -q --junitxml=test-results.xml
        '''
      }
      post { always { junit allowEmptyResults: true, testResults: 'test-results.xml' } }
    }

    stage('Terraform plan & apply') {
      when { expression { params.ACTION in ['deploy', 'plan-only'] } }
      steps {
        withCredentials([sshUserPrivateKey(credentialsId: 'ec2-ssh', keyFileVariable: 'SSH_KEY')]) {
          dir('terraform') {
            sh '''#!/bin/bash
              set -eo pipefail
              export TF_VAR_aws_region="${AWS_REGION}"
              export TF_VAR_ssh_public_key="$(ssh-keygen -y -f "$SSH_KEY")"
              export TF_VAR_jenkins_security_group_id="${JENKINS_SG_ID}"
              export TF_VAR_allowed_ssh_cidrs="${ADMIN_CIDRS_JSON}"

              terraform init -reconfigure -input=false \
                -backend-config="bucket=${TF_STATE_BUCKET}" \
                -backend-config="key=library/terraform.tfstate" \
                -backend-config="region=${AWS_REGION}" \
                -backend-config="encrypt=true" \
                -backend-config="use_lockfile=true"
              terraform plan -input=false -out=tfplan | tee ../plan.txt
              if [ "${ACTION}" = "deploy" ]; then
                terraform apply -input=false tfplan | tee ../apply.txt
                terraform output -raw app_private_ip > ../app_private_ip.txt
              fi
            '''
          }
        }
        script {
          if (params.ACTION == 'deploy') {
            env.EC2_HOST = readFile('app_private_ip.txt').trim()
            echo "App host (private IP): ${env.EC2_HOST}"
          }
        }
      }
    }

    stage('Terraform destroy') {
      when { expression { params.ACTION == 'destroy' } }
      steps {
        input message: 'Destroy ALL Terraform-managed infrastructure (app EC2, ECR repos + images, security group, IAM role)?', ok: 'Destroy'
        withCredentials([sshUserPrivateKey(credentialsId: 'ec2-ssh', keyFileVariable: 'SSH_KEY')]) {
          dir('terraform') {
            sh '''#!/bin/bash
              set -eo pipefail
              export TF_VAR_aws_region="${AWS_REGION}"
              export TF_VAR_ssh_public_key="$(ssh-keygen -y -f "$SSH_KEY")"
              export TF_VAR_jenkins_security_group_id="${JENKINS_SG_ID}"
              export TF_VAR_allowed_ssh_cidrs="${ADMIN_CIDRS_JSON}"

              terraform init -reconfigure -input=false \
                -backend-config="bucket=${TF_STATE_BUCKET}" \
                -backend-config="key=library/terraform.tfstate" \
                -backend-config="region=${AWS_REGION}" \
                -backend-config="encrypt=true" \
                -backend-config="use_lockfile=true"
              terraform destroy -input=false -auto-approve | tee ../destroy.txt
            '''
          }
        }
      }
    }

    stage('Build & tag images') {
      when { expression { params.ACTION == 'deploy' && !params.DEPLOY_TAG } }
      steps {
        sh '''
          set -e
          for s in $SERVICES; do
            docker build -t library/$s:${IMAGE_TAG} ./${s}_service
          done
        '''
      }
    }

    stage('Push to ECR') {
      when { expression { params.ACTION == 'deploy' && !params.DEPLOY_TAG } }
      steps {
        sh '''
          set -e
          aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${REGISTRY}
          for s in $SERVICES; do
            docker tag library/$s:${IMAGE_TAG} ${REGISTRY}/library/$s:${IMAGE_TAG}
            docker push ${REGISTRY}/library/$s:${IMAGE_TAG}
          done
          docker logout ${REGISTRY}
        '''
      }
    }

    stage('Deploy to EC2') {
      when { expression { params.ACTION == 'deploy' } }
      steps {
        sshagent(credentials: ['ec2-ssh']) {
          sh '''#!/bin/bash
            set -eo pipefail
            SSH_OPTS="-o StrictHostKeyChecking=accept-new -o ConnectTimeout=20"

            # A brand-new host is still running its bootstrap (Docker, AWS CLI): wait for it
            for i in $(seq 1 30); do
              ssh $SSH_OPTS ${EC2_USER}@${EC2_HOST} 'test -f /var/log/bootstrap-done' && break
              echo "waiting for host bootstrap ($i/30)"; sleep 20
            done
            ssh $SSH_OPTS ${EC2_USER}@${EC2_HOST} 'test -f /var/log/bootstrap-done'

            tar czf - docker-compose.yml docker-compose.prod.yml docker-compose.monitoring.yml .env.example nginx monitoring scripts \
              | ssh $SSH_OPTS ${EC2_USER}@${EC2_HOST} 'mkdir -p /opt/library && tar xzf - -C /opt/library'
            # Deploy + verify + automatic rollback all happen in deploy.sh; a non-zero exit fails the build
            ssh $SSH_OPTS ${EC2_USER}@${EC2_HOST} \
              "cd /opt/library && ECR_REGISTRY=${REGISTRY} AWS_REGION=${AWS_REGION} bash scripts/deploy.sh ${IMAGE_TAG}" | tee deploy.log
          '''
        }
      }
    }

    stage('Verify from Jenkins') {
      when { expression { params.ACTION == 'deploy' } }
      steps {
        sh '''
          set -e
          for s in users books orders; do
            curl -fsS --retry 5 --retry-delay 3 --max-time 10 http://${EC2_HOST}/api/$s/health
            echo
          done
        '''
      }
    }
  }

  post {
    success { echo "${params.ACTION} finished successfully (${env.IMAGE_TAG})" }
    failure { echo "Pipeline FAILED (${params.ACTION}, ${env.IMAGE_TAG}). See the console log, plan.txt and deploy.log; deploy.sh already attempted automatic rollback." }
    always  { archiveArtifacts artifacts: 'plan.txt, apply.txt, destroy.txt, deploy.log, test-results.xml', allowEmptyArchive: true }
  }
}
