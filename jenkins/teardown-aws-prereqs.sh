#!/usr/bin/env bash
# Run AFTER the pipeline's ACTION=destroy build and after terminating the Jenkins EC2.
# Removes the state bucket, Jenkins role/policy/instance profile. Usage: bash jenkins/teardown-aws-prereqs.sh
set -uo pipefail
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
BUCKET="library-tfstate-${ACCOUNT}"
POLICY_ARN="arn:aws:iam::${ACCOUNT}:policy/jenkins-ci-policy"
aws iam remove-role-from-instance-profile --instance-profile-name jenkins-ec2-profile --role-name jenkins-ec2-role
aws iam delete-instance-profile --instance-profile-name jenkins-ec2-profile
aws iam detach-role-policy --role-name jenkins-ec2-role --policy-arn "$POLICY_ARN"
aws iam delete-role --role-name jenkins-ec2-role
for v in $(aws iam list-policy-versions --policy-arn "$POLICY_ARN" --query 'Versions[?IsDefaultVersion==`false`].VersionId' --output text); do
  aws iam delete-policy-version --policy-arn "$POLICY_ARN" --version-id "$v"
done
aws iam delete-policy --policy-arn "$POLICY_ARN"
aws s3 rb "s3://${BUCKET}" --force
echo "Prerequisites removed. Check the console for leftovers (EC2, EBS, ECR, S3, IAM)."
