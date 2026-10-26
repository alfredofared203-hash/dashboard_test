resource "aws_ecr_repository" "test_lab" {
  name                 = var.ecr_repository_name
  image_tag_mutability = "IMMUTABLE"
  force_delete         = false

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Name = var.ecr_repository_name
  }
}

resource "aws_ecr_repository" "dcc_app" {
  name                 = "dcc-app"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = false

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Name        = "dcc-app"
    Project     = "DCC"
    Environment = "application"
    ManagedBy   = "IaC"
    Purpose     = "dcc-application-image"
  }
}

resource "aws_ecr_lifecycle_policy" "test_lab" {
  repository = aws_ecr_repository.test_lab.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire old images beyond the configured retention count."
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = var.ecr_lifecycle_image_count
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
