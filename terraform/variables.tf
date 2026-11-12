variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Prefix used for resource names and tags"
  type        = string
  default     = "library"
}

variable "instance_type" {
  description = "EC2 instance type (check Free Tier eligibility for your account)"
  type        = string
  default     = "t3.small"
}

variable "root_volume_size_gb" {
  description = "Root EBS volume size"
  type        = number
  default     = 20
}

variable "ssh_public_key" {
  description = "Contents of your SSH PUBLIC key (never the private key)"
  type        = string
}

variable "allowed_ssh_cidrs" {
  description = "Admin CIDRs allowed to SSH (your own IP, for the monitoring tunnel), e.g. [\"203.0.113.10/32\"]. Jenkins is allowed separately via jenkins_security_group_id."
  type        = list(string)
  default     = []
}

variable "jenkins_security_group_id" {
  description = "Security group of the manually created Jenkins EC2 (same VPC). It is allowed SSH (deploy) and HTTP (verification) to the app host. Empty = no rule."
  type        = string
  default     = ""
}

variable "allowed_http_cidrs" {
  description = "CIDRs allowed to reach Nginx on port 80"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "services" {
  description = "Microservices that each get an ECR repository"
  type        = list(string)
  default     = ["users", "books", "orders"]
}

variable "monthly_budget_usd" {
  description = "Monthly cost budget in USD"
  type        = number
  default     = 10
}

variable "budget_email" {
  description = "Email for budget alerts. Leave empty to skip creating the budget."
  type        = string
  default     = ""
}
