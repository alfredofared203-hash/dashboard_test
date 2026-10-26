locals {
  test_app_image = "${aws_ecr_repository.test_lab.repository_url}@${var.test_app_image_digest}"

  test_app_database_url = "postgresql://${var.rds_master_username}@${aws_db_instance.test_lab.address}:${aws_db_instance.test_lab.port}/${var.rds_database_name}"
  test_app_redis_url    = "rediss://${aws_elasticache_replication_group.test_lab.primary_endpoint_address}:${aws_elasticache_replication_group.test_lab.port}/0"
}

resource "aws_cloudwatch_log_group" "test_api" {
  name              = "${var.log_group_prefix}/api"
  retention_in_days = 7

  tags = {
    Name = "${var.name_prefix}-api"
  }
}

resource "aws_cloudwatch_log_group" "test_worker" {
  name              = "${var.log_group_prefix}/worker"
  retention_in_days = 7

  tags = {
    Name = "${var.name_prefix}-worker"
  }
}

resource "aws_ecs_cluster" "test_lab" {
  name = "${var.name_prefix}-cluster"

  tags = {
    Name = "${var.name_prefix}-cluster"
  }
}

resource "aws_ecs_task_definition" "test_api" {
  family                   = "${var.name_prefix}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.test_api_task.arn

  container_definitions = jsonencode([
    {
      name      = "api"
      image     = local.test_app_image
      essential = true
      environment = [
        { name = "APP_NAME", value = "standalone-test-laboratory" },
        { name = "APP_VERSION", value = "0.1.0" },
        { name = "ENVIRONMENT", value = var.environment_name },
        { name = "LOG_LEVEL", value = "INFO" },
        { name = "SERVICE_NAME", value = "api-service" },
        { name = "HOST", value = "0.0.0.0" },
        { name = "PORT", value = tostring(var.test_api_port) },
        { name = "REQUEST_TIMEOUT_MS", value = "3000" },
        { name = "DATABASE_URL", value = local.test_app_database_url },
        { name = "REDIS_URL", value = local.test_app_redis_url },
        { name = "WORKER_ENABLED", value = "false" },
        { name = "MAX_CPU_WORK_MS", value = "1000" },
        { name = "MAX_LATENCY_MS", value = "1000" },
        { name = "MAX_MEMORY_MB", value = "32" },
      ]
      secrets = [
        {
          name      = "PGPASSWORD"
          valueFrom = "${aws_db_instance.test_lab.master_user_secret[0].secret_arn}:password::"
        }
      ]
      portMappings = [
        {
          name          = "http"
          containerPort = var.test_api_port
          hostPort      = var.test_api_port
          protocol      = "tcp"
        }
      ]
      healthCheck = {
        command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:${var.test_api_port}/health', timeout=3)\""]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 30
      }
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.test_api.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "api"
        }
      }
    }
  ])

  tags = {
    Name = "${var.name_prefix}-api"
  }
}

resource "aws_ecs_task_definition" "test_worker" {
  family                   = "${var.name_prefix}-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.test_worker_task.arn

  container_definitions = jsonencode([
    {
      name      = "worker"
      image     = local.test_app_image
      essential = true
      command   = ["python", "-m", "worker.main"]
      environment = [
        { name = "APP_NAME", value = "standalone-test-laboratory" },
        { name = "APP_VERSION", value = "0.1.0" },
        { name = "ENVIRONMENT", value = var.environment_name },
        { name = "LOG_LEVEL", value = "INFO" },
        { name = "SERVICE_NAME", value = "worker-service" },
        { name = "DATABASE_URL", value = local.test_app_database_url },
        { name = "REDIS_URL", value = local.test_app_redis_url },
        { name = "WORKER_ENABLED", value = "true" },
        { name = "WORKER_INTERVAL_SECONDS", value = "10" },
        { name = "WORKER_METRICS_PORT", value = "9101" },
      ]
      secrets = [
        {
          name      = "PGPASSWORD"
          valueFrom = "${aws_db_instance.test_lab.master_user_secret[0].secret_arn}:password::"
        }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.test_worker.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "worker"
        }
      }
    }
  ])

  tags = {
    Name = "${var.name_prefix}-worker"
  }
}

resource "aws_ecs_service" "test_api" {
  name            = "api-service"
  cluster         = aws_ecs_cluster.test_lab.id
  task_definition = aws_ecs_task_definition.test_api.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = [for subnet in aws_subnet.private_application : subnet.id]
    security_groups  = [aws_security_group.test_api.id]
    assign_public_ip = false
  }

  service_registries {
    registry_arn = aws_service_discovery_service.test_api.arn
  }

  depends_on = [
    aws_cloudwatch_log_group.test_api,
    aws_iam_role_policy.ecs_database_secret,
  ]

  tags = {
    Name = "${var.name_prefix}-api-service"
  }
}

resource "aws_ecs_service" "test_worker" {
  name            = "worker-service"
  cluster         = aws_ecs_cluster.test_lab.id
  task_definition = aws_ecs_task_definition.test_worker.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = [for subnet in aws_subnet.private_application : subnet.id]
    security_groups  = [aws_security_group.test_worker.id]
    assign_public_ip = false
  }

  depends_on = [
    aws_cloudwatch_log_group.test_worker,
    aws_iam_role_policy.ecs_database_secret,
  ]

  tags = {
    Name = "${var.name_prefix}-worker-service"
  }
}
