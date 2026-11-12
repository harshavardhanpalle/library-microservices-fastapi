output "ec2_public_ip" {
  description = "Public IP of the app host"
  value       = aws_instance.app.public_ip
}

output "ssh_command" {
  value = "ssh ubuntu@${aws_instance.app.public_ip}"
}

output "ecr_registry" {
  description = "Registry host for docker login / ECR_REGISTRY"
  value       = split("/", values(aws_ecr_repository.svc)[0].repository_url)[0]
}

output "ecr_repository_urls" {
  value = { for k, r in aws_ecr_repository.svc : k => r.repository_url }
}

output "app_private_ip" {
  description = "Jenkins (same VPC) deploys and verifies through this address"
  value       = aws_instance.app.private_ip
}
