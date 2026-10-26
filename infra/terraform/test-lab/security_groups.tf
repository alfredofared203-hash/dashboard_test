resource "aws_security_group" "dcc_control" {
  name        = "${var.name_prefix}-sg-dcc-control"
  description = "Private DCC ECS control service in the Test Lab VPC."
  vpc_id      = aws_vpc.test_lab.id

  tags = {
    Name = "${var.name_prefix}-sg-dcc-control"
  }
}

resource "aws_security_group" "dcc_alb" {
  name        = "${var.name_prefix}-sg-dcc-alb"
  description = "Public HTTP ingress for the DCC Application Load Balancer only."
  vpc_id      = aws_vpc.test_lab.id

  ingress {
    description = "Public HTTP access to the DCC load balancer."
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description     = "Forward HTTP traffic to private DCC tasks."
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.dcc_control.id]
  }

  tags = {
    Name = "${var.name_prefix}-sg-dcc-alb"
  }
}

resource "aws_security_group" "diagnostic_worker" {
  name        = "${var.name_prefix}-sg-diagnostic-worker"
  description = "On-demand DCC diagnostic worker task."
  vpc_id      = aws_vpc.test_lab.id

  tags = {
    Name = "${var.name_prefix}-sg-diagnostic-worker"
  }
}

resource "aws_security_group" "test_api" {
  name        = "${var.name_prefix}-sg-test-api"
  description = "Private Test Laboratory API task."
  vpc_id      = aws_vpc.test_lab.id

  tags = {
    Name = "${var.name_prefix}-sg-test-api"
  }
}

resource "aws_security_group" "test_worker" {
  name        = "${var.name_prefix}-sg-test-worker"
  description = "Private Test Laboratory background worker."
  vpc_id      = aws_vpc.test_lab.id

  tags = {
    Name = "${var.name_prefix}-sg-test-worker"
  }
}

resource "aws_security_group" "rds" {
  name        = "${var.name_prefix}-sg-rds"
  description = "Private PostgreSQL access from Test Lab application tasks."
  vpc_id      = aws_vpc.test_lab.id

  tags = {
    Name = "${var.name_prefix}-sg-rds"
  }
}

resource "aws_security_group" "redis" {
  name        = "${var.name_prefix}-sg-redis"
  description = "Private Redis-compatible cache access from Test Lab application tasks."
  vpc_id      = aws_vpc.test_lab.id

  tags = {
    Name = "${var.name_prefix}-sg-redis"
  }
}

resource "aws_vpc_security_group_ingress_rule" "test_api_from_diagnostic_worker" {
  security_group_id            = aws_security_group.test_api.id
  referenced_security_group_id = aws_security_group.diagnostic_worker.id
  description                  = "Diagnostic worker to a selected Test API task."
  ip_protocol                  = "tcp"
  from_port                    = var.test_api_port
  to_port                      = var.test_api_port
}

resource "aws_vpc_security_group_ingress_rule" "test_api_from_dcc_control" {
  security_group_id            = aws_security_group.test_api.id
  referenced_security_group_id = aws_security_group.dcc_control.id
  description                  = "DCC control service to the private Test API."
  ip_protocol                  = "tcp"
  from_port                    = var.test_api_port
  to_port                      = var.test_api_port
}

resource "aws_vpc_security_group_ingress_rule" "dcc_app_from_alb" {
  security_group_id            = aws_security_group.dcc_control.id
  referenced_security_group_id = aws_security_group.dcc_alb.id
  description                  = "Only the public DCC ALB may reach the private DCC application."
  ip_protocol                  = "tcp"
  from_port                    = 8000
  to_port                      = 8000
}

resource "aws_vpc_security_group_ingress_rule" "rds_from_test_api" {
  security_group_id            = aws_security_group.rds.id
  referenced_security_group_id = aws_security_group.test_api.id
  description                  = "Test API to PostgreSQL."
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
}

resource "aws_vpc_security_group_ingress_rule" "rds_from_test_worker" {
  security_group_id            = aws_security_group.rds.id
  referenced_security_group_id = aws_security_group.test_worker.id
  description                  = "Test Worker to PostgreSQL."
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
}

resource "aws_vpc_security_group_ingress_rule" "redis_from_test_api" {
  security_group_id            = aws_security_group.redis.id
  referenced_security_group_id = aws_security_group.test_api.id
  description                  = "Test API to Redis-compatible cache."
  ip_protocol                  = "tcp"
  from_port                    = 6379
  to_port                      = 6379
}

resource "aws_vpc_security_group_ingress_rule" "redis_from_test_worker" {
  security_group_id            = aws_security_group.redis.id
  referenced_security_group_id = aws_security_group.test_worker.id
  description                  = "Test Worker to Redis-compatible cache."
  ip_protocol                  = "tcp"
  from_port                    = 6379
  to_port                      = 6379
}

resource "aws_vpc_security_group_egress_rule" "diagnostic_worker_https" {
  security_group_id = aws_security_group.diagnostic_worker.id
  description       = "HTTPS access for required AWS APIs and approved external endpoints."
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_vpc_security_group_egress_rule" "dcc_control_https" {
  security_group_id = aws_security_group.dcc_control.id
  description       = "HTTPS access to AWS APIs through the private application subnet egress path."
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_vpc_security_group_egress_rule" "dcc_control_test_api" {
  security_group_id            = aws_security_group.dcc_control.id
  referenced_security_group_id = aws_security_group.test_api.id
  description                  = "DCC control service to the private Test API."
  ip_protocol                  = "tcp"
  from_port                    = var.test_api_port
  to_port                      = var.test_api_port
}

resource "aws_vpc_security_group_egress_rule" "diagnostic_worker_test_api" {
  security_group_id            = aws_security_group.diagnostic_worker.id
  referenced_security_group_id = aws_security_group.test_api.id
  description                  = "Diagnostic worker to selected Test API task."
  ip_protocol                  = "tcp"
  from_port                    = var.test_api_port
  to_port                      = var.test_api_port
}

resource "aws_vpc_security_group_egress_rule" "test_api_https" {
  security_group_id = aws_security_group.test_api.id
  description       = "HTTPS access for image startup, logs, and approved AWS endpoints."
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_vpc_security_group_egress_rule" "test_api_rds" {
  security_group_id            = aws_security_group.test_api.id
  referenced_security_group_id = aws_security_group.rds.id
  description                  = "Test API to PostgreSQL."
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
}

resource "aws_vpc_security_group_egress_rule" "test_api_redis" {
  security_group_id            = aws_security_group.test_api.id
  referenced_security_group_id = aws_security_group.redis.id
  description                  = "Test API to Redis-compatible cache."
  ip_protocol                  = "tcp"
  from_port                    = 6379
  to_port                      = 6379
}

resource "aws_vpc_security_group_egress_rule" "test_worker_https" {
  security_group_id = aws_security_group.test_worker.id
  description       = "HTTPS access for image startup, logs, and approved AWS endpoints."
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_vpc_security_group_egress_rule" "test_worker_rds" {
  security_group_id            = aws_security_group.test_worker.id
  referenced_security_group_id = aws_security_group.rds.id
  description                  = "Test Worker to PostgreSQL."
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
}

resource "aws_vpc_security_group_egress_rule" "test_worker_redis" {
  security_group_id            = aws_security_group.test_worker.id
  referenced_security_group_id = aws_security_group.redis.id
  description                  = "Test Worker to Redis-compatible cache."
  ip_protocol                  = "tcp"
  from_port                    = 6379
  to_port                      = 6379
}
