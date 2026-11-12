# Jenkins build server on its own small EC2 instance (per trainer's instruction).
# UI (8080) and SSH are reachable ONLY from allowed_ssh_cidrs. Set create_jenkins_host=false
# to run Jenkins on your own workstation instead.

resource "aws_security_group" "jenkins" {
  count       = var.create_jenkins_host ? 1 : 0
  name        = "${var.project_name}-jenkins-sg"
  description = "Jenkins UI and SSH from approved IPs only"
  vpc_id      = data.aws_vpc.default.id
}

resource "aws_vpc_security_group_ingress_rule" "jenkins_ui" {
  for_each          = var.create_jenkins_host ? toset(var.allowed_ssh_cidrs) : toset([])
  security_group_id = aws_security_group.jenkins[0].id
  description       = "Jenkins UI from approved IP"
  cidr_ipv4         = each.value
  from_port         = 8080
  to_port           = 8080
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "jenkins_ssh" {
  for_each          = var.create_jenkins_host ? toset(var.allowed_ssh_cidrs) : toset([])
  security_group_id = aws_security_group.jenkins[0].id
  description       = "SSH from approved IP"
  cidr_ipv4         = each.value
  from_port         = 22
  to_port           = 22
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "jenkins_https" {
  count             = var.create_jenkins_host ? 1 : 0
  security_group_id = aws_security_group.jenkins[0].id
  description       = "HTTPS (plugins, ECR, Docker Hub)"
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "jenkins_http" {
  count             = var.create_jenkins_host ? 1 : 0
  security_group_id = aws_security_group.jenkins[0].id
  description       = "HTTP (apt)"
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "jenkins_dns" {
  count             = var.create_jenkins_host ? 1 : 0
  security_group_id = aws_security_group.jenkins[0].id
  description       = "DNS"
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 53
  to_port           = 53
  ip_protocol       = "udp"
}

resource "aws_vpc_security_group_egress_rule" "jenkins_ntp" {
  count             = var.create_jenkins_host ? 1 : 0
  security_group_id = aws_security_group.jenkins[0].id
  description       = "NTP"
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 123
  to_port           = 123
  ip_protocol       = "udp"
}

resource "aws_vpc_security_group_egress_rule" "jenkins_to_app_ssh" {
  count                        = var.create_jenkins_host ? 1 : 0
  security_group_id            = aws_security_group.jenkins[0].id
  description                  = "SSH to the app host (deploy)"
  referenced_security_group_id = aws_security_group.app.id
  from_port                    = 22
  to_port                      = 22
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "jenkins_to_app_http" {
  count                        = var.create_jenkins_host ? 1 : 0
  security_group_id            = aws_security_group.jenkins[0].id
  description                  = "HTTP to the app host (deployment verification)"
  referenced_security_group_id = aws_security_group.app.id
  from_port                    = 80
  to_port                      = 80
  ip_protocol                  = "tcp"
}

# Allow Jenkins (by security group, i.e. private IP) to SSH and curl the app host
resource "aws_vpc_security_group_ingress_rule" "app_ssh_from_jenkins" {
  count                        = var.create_jenkins_host ? 1 : 0
  security_group_id            = aws_security_group.app.id
  description                  = "SSH from Jenkins host"
  referenced_security_group_id = aws_security_group.jenkins[0].id
  from_port                    = 22
  to_port                      = 22
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "app_http_from_jenkins" {
  count                        = var.create_jenkins_host ? 1 : 0
  security_group_id            = aws_security_group.app.id
  description                  = "HTTP from Jenkins host (verification)"
  referenced_security_group_id = aws_security_group.jenkins[0].id
  from_port                    = 80
  to_port                      = 80
  ip_protocol                  = "tcp"
}

resource "aws_instance" "jenkins" {
  count                       = var.create_jenkins_host ? 1 : 0
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = var.jenkins_instance_type
  subnet_id                   = data.aws_subnets.default.ids[0]
  vpc_security_group_ids      = [aws_security_group.jenkins[0].id]
  key_name                    = aws_key_pair.deploy.key_name
  associate_public_ip_address = true
  user_data                   = file("${path.module}/userdata_jenkins.sh")

  metadata_options {
    http_tokens = "required"
  }

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
    encrypted   = true
  }

  tags = {
    Name = "${var.project_name}-jenkins"
  }
}
