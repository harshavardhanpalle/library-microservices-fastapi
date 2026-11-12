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

output "jenkins_iam_user" {
  description = "Create an access key for this user in the console and store it in Jenkins"
  value       = aws_iam_user.jenkins.name
}

output "app_private_ip" {
  description = "Use THIS as the Jenkins 'ec2-host' credential when Jenkins runs on EC2 (same VPC)"
  value       = aws_instance.app.private_ip
}

output "jenkins_url" {
  value = var.create_jenkins_host ? "http://${aws_instance.jenkins[0].public_ip}:8080" : "Jenkins host not created"
}

output "jenkins_ssh" {
  value = var.create_jenkins_host ? "ssh ubuntu@${aws_instance.jenkins[0].public_ip}" : "n/a"
}
