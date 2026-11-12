#!/usr/bin/env bash
# Run ONCE from your laptop with admin credentials (aws configure). Creates:
#   - S3 bucket for Terraform state        : library-tfstate-<account-id>
#   - IAM policy / role / instance profile : jenkins-ci-policy / jenkins-ec2-role / jenkins-ec2-profile
# Attach the instance profile to your manually created Jenkins EC2. No access keys are created.
# Usage: bash jenkins/setup-aws-prereqs.sh [region]
set -euo pipefail
cd "$(dirname "$0")"

REGION="${1:-${AWS_REGION:-ap-south-1}}"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
BUCKET="library-tfstate-${ACCOUNT}"
POLICY_NAME="jenkins-ci-policy"
ROLE_NAME="jenkins-ec2-role"
PROFILE_NAME="jenkins-ec2-profile"
POLICY_ARN="arn:aws:iam::${ACCOUNT}:policy/${POLICY_NAME}"

echo "Account: ${ACCOUNT}  Region: ${REGION}"

echo "== 1/4 S3 bucket for Terraform state (${BUCKET})"
if aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  echo "bucket already exists"
else
  if [ "$REGION" = "us-east-1" ]; then
    aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" >/dev/null
  else
    aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" \
      --create-bucket-configuration LocationConstraint="$REGION" >/dev/null
  fi
fi
aws s3api put-public-access-block --bucket "$BUCKET" --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3api put-bucket-encryption --bucket "$BUCKET" --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

echo "== 2/4 IAM policy (${POLICY_NAME})"
TMP="$(mktemp)"
sed "s/__STATE_BUCKET__/${BUCKET}/g" iam/jenkins-policy.json > "$TMP"
if aws iam get-policy --policy-arn "$POLICY_ARN" >/dev/null 2>&1; then
  # keep at most 5 versions: remove the oldest non-default one if needed
  OLD="$(aws iam list-policy-versions --policy-arn "$POLICY_ARN" \
    --query 'Versions[?IsDefaultVersion==`false`]|[-1].VersionId' --output text)"
  COUNT="$(aws iam list-policy-versions --policy-arn "$POLICY_ARN" --query 'length(Versions)' --output text)"
  if [ "$COUNT" -ge 5 ] && [ "$OLD" != "None" ]; then
    aws iam delete-policy-version --policy-arn "$POLICY_ARN" --version-id "$OLD"
  fi
  aws iam create-policy-version --policy-arn "$POLICY_ARN" --policy-document "file://$TMP" --set-as-default >/dev/null
  echo "policy updated"
else
  aws iam create-policy --policy-name "$POLICY_NAME" --policy-document "file://$TMP" >/dev/null
  echo "policy created"
fi
rm -f "$TMP"

echo "== 3/4 IAM role (${ROLE_NAME})"
if ! aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
  aws iam create-role --role-name "$ROLE_NAME" \
    --assume-role-policy-document file://iam/trust-policy-ec2.json >/dev/null
fi
aws iam attach-role-policy --role-name "$ROLE_NAME" --policy-arn "$POLICY_ARN"

echo "== 4/4 Instance profile (${PROFILE_NAME})"
if ! aws iam get-instance-profile --instance-profile-name "$PROFILE_NAME" >/dev/null 2>&1; then
  aws iam create-instance-profile --instance-profile-name "$PROFILE_NAME" >/dev/null
  aws iam add-role-to-instance-profile --instance-profile-name "$PROFILE_NAME" --role-name "$ROLE_NAME"
fi

cat <<MSG

Done. Next:
  1. Launch the Jenkins EC2 in the DEFAULT VPC with IAM instance profile: ${PROFILE_NAME}
     (see jenkins/SETUP.md). Terraform state bucket the pipeline will use: ${BUCKET}
  2. Run jenkins/bootstrap-jenkins.sh on that instance (or paste it as User data).
MSG
