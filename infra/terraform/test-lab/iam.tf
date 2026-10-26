data "aws_iam_policy_document" "ecs_tasks_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ecs_execution" {
  name               = "${var.name_prefix}-execution-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_trust.json

  tags = {
    Name = "${var.name_prefix}-execution-role"
  }
}

data "aws_iam_policy_document" "ecs_execution" {
  statement {
    sid       = "ECRAuthorization"
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid    = "PullTestLabImage"
    effect = "Allow"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage",
    ]
    resources = [aws_ecr_repository.test_lab.arn]
  }

  statement {
    sid    = "PullDCCImage"
    effect = "Allow"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage",
    ]
    resources = [aws_ecr_repository.dcc_app.arn]
  }

  statement {
    sid    = "WriteTestLabLogs"
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = [
      "arn:${data.aws_partition.current.partition}:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:${var.log_group_prefix}/*:log-stream:*"
    ]
  }

  statement {
    sid       = "ReadDCCApplicationSecret"
    effect    = "Allow"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.dcc_django_key.arn]
  }
}

resource "aws_iam_role_policy" "ecs_execution" {
  name   = "${var.name_prefix}-execution-policy"
  role   = aws_iam_role.ecs_execution.id
  policy = data.aws_iam_policy_document.ecs_execution.json
}

data "aws_iam_policy_document" "ecs_database_secret" {
  statement {
    sid       = "ReadManagedDatabaseCredentials"
    effect    = "Allow"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_db_instance.test_lab.master_user_secret[0].secret_arn]
  }
}

resource "aws_iam_role_policy" "ecs_database_secret" {
  name   = "${var.name_prefix}-database-secret-policy"
  role   = aws_iam_role.ecs_execution.id
  policy = data.aws_iam_policy_document.ecs_database_secret.json
}

resource "aws_iam_role" "test_api_task" {
  name               = "${var.name_prefix}-api-task-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_trust.json

  tags = {
    Name = "${var.name_prefix}-api-task-role"
  }
}

resource "aws_iam_role" "test_worker_task" {
  name               = "${var.name_prefix}-worker-task-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_trust.json

  tags = {
    Name = "${var.name_prefix}-worker-task-role"
  }
}

resource "aws_iam_role" "diagnostic_task" {
  name               = "${var.name_prefix}-diagnostic-task-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_trust.json

  tags = {
    Name = "${var.name_prefix}-diagnostic-task-role"
  }
}

data "aws_iam_policy_document" "dcc_ecs_discovery" {
  statement {
    sid       = "DiscoverConfiguredCluster"
    effect    = "Allow"
    actions   = ["ecs:DescribeClusters"]
    resources = [aws_ecs_cluster.test_lab.arn]
  }

  statement {
    sid       = "ListConfiguredServices"
    effect    = "Allow"
    actions   = ["ecs:ListServices"]
    resources = [aws_ecs_cluster.test_lab.arn, "arn:${data.aws_partition.current.partition}:ecs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:service/${aws_ecs_cluster.test_lab.name}/*"]
  }

  statement {
    sid     = "ListConfiguredTasks"
    effect  = "Allow"
    actions = ["ecs:ListTasks"]
    resources = [
      aws_ecs_cluster.test_lab.arn,
      "arn:${data.aws_partition.current.partition}:ecs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:container-instance/${aws_ecs_cluster.test_lab.name}/*",
    ]
  }

  statement {
    sid    = "DescribeConfiguredServicesAndTasks"
    effect = "Allow"
    actions = [
      "ecs:DescribeServices",
      "ecs:DescribeTasks",
    ]
    resources = [
      aws_ecs_cluster.test_lab.arn,
      "arn:${data.aws_partition.current.partition}:ecs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:service/${aws_ecs_cluster.test_lab.name}/*",
      "arn:${data.aws_partition.current.partition}:ecs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:task/${aws_ecs_cluster.test_lab.name}/*",
    ]
  }

  statement {
    sid       = "DescribeConfiguredTaskDefinitions"
    effect    = "Allow"
    actions   = ["ecs:DescribeTaskDefinition"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "dcc_ecs_discovery" {
  name   = "${var.name_prefix}-dcc-ecs-discovery-policy"
  role   = aws_iam_role.diagnostic_task.id
  policy = data.aws_iam_policy_document.dcc_ecs_discovery.json
}
