terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Local state is used for this assignment (terraform.tfstate is git-ignored).
  # For team use, switch to a remote backend, e.g.:
  # backend "s3" {
  #   bucket         = "<your-state-bucket>"
  #   key            = "library/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "<lock-table>"
  #   encrypt        = true
  # }
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
