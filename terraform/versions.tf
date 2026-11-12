terraform {
  required_version = ">= 1.10.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Remote state in S3 (bucket created once by jenkins/setup-aws-prereqs.sh).
  # Values are passed by the Jenkins pipeline: terraform init -backend-config="bucket=..." etc.
  # Native S3 state locking (use_lockfile) needs Terraform >= 1.10. State never goes to Git.
  backend "s3" {}
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = var.project_name
      ManagedBy = "terraform"
    }
  }
}
