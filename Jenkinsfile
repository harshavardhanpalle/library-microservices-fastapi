pipeline {
  agent any

  options {
    timestamps()
    disableConcurrentBuilds()
    buildDiscarder(logRotator(numToKeepStr: '20'))
    timeout(time: 30, unit: 'MINUTES')
  }

  // Webhook trigger (needs Jenkins reachable by GitHub) + polling as a fallback
  triggers {
    githubPush()
    pollSCM('H/5 * * * *')
  }

  parameters {
    string(name: 'AWS_REGION', defaultValue: 'us-east-1', description: 'AWS region of the ECR repos / EC2')
    string(name: 'DEPLOY_TAG', defaultValue: '', description: 'Optional: deploy an EXISTING image tag from ECR (skips build/push). Use for rollback.')
  }

  environment {
    EC2_USER = 'ubuntu'
    SERVICES = 'users books orders'
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm
        script {
          env.GIT_SHORT = sh(returnStdout: true, script: 'git rev-parse --short HEAD').trim()
          env.IMAGE_TAG = params.DEPLOY_TAG ?: "${env.BUILD_NUMBER}-${env.GIT_SHORT}"
          echo "Image tag for this run: ${env.IMAGE_TAG}"
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
          for f in scripts/*.sh; do bash -n "$f"; done
          rm -f .env .env.monitoring.ci
        '''
      }
    }

    stage('Test') {
      when { expression { !params.DEPLOY_TAG } }
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

    stage('Build & tag images') {
      when { expression { !params.DEPLOY_TAG } }
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
      when { expression { !params.DEPLOY_TAG } }
      steps {
        withCredentials([usernamePassword(credentialsId: 'aws-jenkins', usernameVariable: 'AWS_ACCESS_KEY_ID', passwordVariable: 'AWS_SECRET_ACCESS_KEY')]) {
          sh '''
            set -e
            export AWS_DEFAULT_REGION=${AWS_REGION}
            ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
            REGISTRY=${ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com
            aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${REGISTRY}
            for s in $SERVICES; do
              docker tag library/$s:${IMAGE_TAG} ${REGISTRY}/library/$s:${IMAGE_TAG}
              docker push ${REGISTRY}/library/$s:${IMAGE_TAG}
            done
            docker logout ${REGISTRY}
          '''
        }
      }
    }

    stage('Deploy to EC2') {
      steps {
        withCredentials([
          usernamePassword(credentialsId: 'aws-jenkins', usernameVariable: 'AWS_ACCESS_KEY_ID', passwordVariable: 'AWS_SECRET_ACCESS_KEY'),
          string(credentialsId: 'ec2-host', variable: 'EC2_HOST')
        ]) {
          sshagent(credentials: ['ec2-ssh']) {
            sh '''
              set -e
              export AWS_DEFAULT_REGION=${AWS_REGION}
              ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
              REGISTRY=${ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com
              SSH_OPTS="-o StrictHostKeyChecking=accept-new -o ConnectTimeout=20"

              ssh $SSH_OPTS ${EC2_USER}@${EC2_HOST} 'mkdir -p /opt/library'
              tar czf - docker-compose.yml docker-compose.prod.yml docker-compose.monitoring.yml .env.example nginx monitoring scripts \
                | ssh $SSH_OPTS ${EC2_USER}@${EC2_HOST} 'tar xzf - -C /opt/library'
              # Deploy + verify + automatic rollback all happen in deploy.sh; a non-zero exit fails the build
              ssh $SSH_OPTS ${EC2_USER}@${EC2_HOST} \
                "cd /opt/library && ECR_REGISTRY=${REGISTRY} AWS_REGION=${AWS_REGION} bash scripts/deploy.sh ${IMAGE_TAG}" | tee deploy.log
            '''
          }
        }
      }
    }

    stage('Verify from Jenkins') {
      steps {
        withCredentials([string(credentialsId: 'ec2-host', variable: 'EC2_HOST')]) {
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
  }

  post {
    success { echo "Deployed ${env.IMAGE_TAG} successfully" }
    failure { echo "Pipeline FAILED for ${env.IMAGE_TAG}. See deploy.log; deploy.sh already attempted automatic rollback." }
    always  { archiveArtifacts artifacts: 'deploy.log, test-results.xml', allowEmptyArchive: true }
  }
}
