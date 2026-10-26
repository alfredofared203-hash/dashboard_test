output "aws_region" {
  description = "AWS region selected for the Test Lab."
  value       = var.aws_region
}

output "vpc_id" {
  description = "Dedicated DCC and Test Lab VPC ID."
  value       = aws_vpc.test_lab.id
}

output "vpc_cidr" {
  description = "Dedicated DCC and Test Lab VPC CIDR."
  value       = aws_vpc.test_lab.cidr_block
}

output "availability_zones" {
  description = "Availability Zone names selected for the Test Lab."
  value       = local.availability_zones
}

output "public_subnet_ids" {
  description = "Public subnet IDs."
  value       = [for index in range(length(local.availability_zones)) : aws_subnet.public[tostring(index)].id]
}

output "private_application_subnet_ids" {
  description = "Private application subnet IDs for ECS tasks."
  value       = [for index in range(length(local.availability_zones)) : aws_subnet.private_application[tostring(index)].id]
}

output "private_data_subnet_ids" {
  description = "Private data subnet IDs for RDS and ElastiCache subnet groups."
  value       = [for index in range(length(local.availability_zones)) : aws_subnet.private_data[tostring(index)].id]
}

output "nat_gateway_id" {
  description = "Single NAT Gateway ID, or null when NAT is disabled."
  value       = var.enable_nat_gateway ? aws_nat_gateway.test_lab[0].id : null
}

output "security_group_ids" {
  description = "Dedicated DCC and Test Lab security group IDs."
  value = {
    dcc_control       = aws_security_group.dcc_control.id
    dcc_alb           = aws_security_group.dcc_alb.id
    diagnostic_worker = aws_security_group.diagnostic_worker.id
    test_api          = aws_security_group.test_api.id
    test_worker       = aws_security_group.test_worker.id
    rds               = aws_security_group.rds.id
    redis             = aws_security_group.redis.id
  }
}

output "ecr_repository_url" {
  description = "Shared API/worker Test Lab image repository URL."
  value       = aws_ecr_repository.test_lab.repository_url
}

output "ecr_repository_arn" {
  description = "Shared API/worker Test Lab image repository ARN."
  value       = aws_ecr_repository.test_lab.arn
}

output "cloud_map_namespace_id" {
  description = "Private Cloud Map namespace ID."
  value       = aws_service_discovery_private_dns_namespace.test_lab.id
}

output "cloud_map_namespace_name" {
  description = "Private Cloud Map namespace DNS name."
  value       = aws_service_discovery_private_dns_namespace.test_lab.name
}

output "cloud_map_test_api_service_id" {
  description = "Cloud Map service ID for future ECS Test API registration."
  value       = aws_service_discovery_service.test_api.id
}

output "iam_role_arns" {
  description = "Foundation IAM role ARNs; no application or DCC administrative permissions are attached to task roles."
  value = {
    execution        = aws_iam_role.ecs_execution.arn
    test_api_task    = aws_iam_role.test_api_task.arn
    test_worker_task = aws_iam_role.test_worker_task.arn
    diagnostic_task  = aws_iam_role.diagnostic_task.arn
  }
}

output "rds_identifier" {
  description = "Private PostgreSQL DB instance identifier."
  value       = aws_db_instance.test_lab.identifier
}

output "rds_endpoint" {
  description = "Private PostgreSQL endpoint address."
  value       = aws_db_instance.test_lab.address
}

output "rds_port" {
  description = "PostgreSQL listener port."
  value       = aws_db_instance.test_lab.port
}

output "rds_subnet_group_name" {
  description = "Private PostgreSQL DB subnet group name."
  value       = aws_db_subnet_group.test_lab.name
}

output "redis_replication_group_id" {
  description = "Single-node Redis-compatible replication group identifier."
  value       = aws_elasticache_replication_group.test_lab.id
}

output "redis_primary_endpoint" {
  description = "Private Redis-compatible primary endpoint address."
  value       = aws_elasticache_replication_group.test_lab.primary_endpoint_address
}

output "redis_port" {
  description = "Redis-compatible cache listener port."
  value       = aws_elasticache_replication_group.test_lab.port
}

output "redis_subnet_group_name" {
  description = "Private Redis-compatible cache subnet group name."
  value       = aws_elasticache_subnet_group.test_lab.name
}

output "ecs_cluster_name" {
  description = "Test Lab ECS cluster name."
  value       = aws_ecs_cluster.test_lab.name
}

output "ecs_api_service_name" {
  description = "Private Test Lab API ECS service name."
  value       = aws_ecs_service.test_api.name
}

output "ecs_worker_service_name" {
  description = "Private Test Lab Worker ECS service name."
  value       = aws_ecs_service.test_worker.name
}

output "ecs_api_task_definition_arn" {
  description = "Test Lab API task definition ARN."
  value       = aws_ecs_task_definition.test_api.arn
}

output "ecs_worker_task_definition_arn" {
  description = "Test Lab Worker task definition ARN."
  value       = aws_ecs_task_definition.test_worker.arn
}

output "ecs_api_log_group_name" {
  description = "Test Lab API CloudWatch log group."
  value       = aws_cloudwatch_log_group.test_api.name
}

output "ecs_worker_log_group_name" {
  description = "Test Lab Worker CloudWatch log group."
  value       = aws_cloudwatch_log_group.test_worker.name
}

output "dcc_alb_dns_name" {
  description = "Public AWS-provided DNS name for the DCC Application Load Balancer."
  value       = aws_lb.dcc.dns_name
}

output "dcc_alb_url" {
  description = "HTTP URL for the public DCC Application Load Balancer."
  value       = "http://${aws_lb.dcc.dns_name}/"
}
