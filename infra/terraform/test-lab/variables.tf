variable "aws_region" {
  description = "AWS region for the isolated Test Lab."
  type        = string
  default     = "eu-north-1"
}

variable "project_name" {
  description = "Project tag value."
  type        = string
  default     = "DCC-TestLab"
}

variable "environment_name" {
  description = "Environment tag value."
  type        = string
  default     = "lab"
}

variable "name_prefix" {
  description = "Stable prefix for Test Lab AWS resource names."
  type        = string
  default     = "dcc-testlab"

  validation {
    condition     = length(var.name_prefix) >= 3 && length(var.name_prefix) <= 32
    error_message = "name_prefix must be between 3 and 32 characters."
  }
}

variable "vpc_cidr" {
  description = "Dedicated VPC CIDR from the approved network design; check all connected networks for overlap."
  type        = string
  default     = "10.80.0.0/16"

  validation {
    condition     = can(cidrnetmask(var.vpc_cidr))
    error_message = "vpc_cidr must be a valid IPv4 CIDR."
  }
}

variable "availability_zones" {
  description = "Exactly two AZ names. Empty selects the first two available names returned for aws_region; do not use AZ IDs."
  type        = list(string)
  default     = []

  validation {
    condition     = length(var.availability_zones) == 0 || (length(var.availability_zones) == 2 && length(distinct(var.availability_zones)) == 2)
    error_message = "availability_zones must be empty or contain exactly two distinct AZ names."
  }
}

variable "public_subnet_cidrs" {
  description = "Public subnet CIDRs, ordered to match availability_zones."
  type        = list(string)
  default     = ["10.80.0.0/24", "10.80.1.0/24"]

  validation {
    condition     = length(var.public_subnet_cidrs) == 2 && alltrue([for cidr in var.public_subnet_cidrs : can(cidrnetmask(cidr))])
    error_message = "public_subnet_cidrs must contain exactly two valid IPv4 CIDRs."
  }
}

variable "private_application_subnet_cidrs" {
  description = "Private application subnet CIDRs, ordered to match availability_zones."
  type        = list(string)
  default     = ["10.80.16.0/20", "10.80.32.0/20"]

  validation {
    condition     = length(var.private_application_subnet_cidrs) == 2 && alltrue([for cidr in var.private_application_subnet_cidrs : can(cidrnetmask(cidr))])
    error_message = "private_application_subnet_cidrs must contain exactly two valid IPv4 CIDRs."
  }
}

variable "private_data_subnet_cidrs" {
  description = "Private data subnet CIDRs, ordered to match availability_zones."
  type        = list(string)
  default     = ["10.80.48.0/24", "10.80.49.0/24"]

  validation {
    condition     = length(var.private_data_subnet_cidrs) == 2 && alltrue([for cidr in var.private_data_subnet_cidrs : can(cidrnetmask(cidr))])
    error_message = "private_data_subnet_cidrs must contain exactly two valid IPv4 CIDRs."
  }
}

variable "enable_nat_gateway" {
  description = "Create one NAT Gateway for private application subnet egress. Disabling it leaves private app tasks without internet egress."
  type        = bool
  default     = true
}

variable "ecr_repository_name" {
  description = "Single shared Test Lab image repository; API and worker use different container commands."
  type        = string
  default     = "dcc-testlab-app"
}

variable "ecr_lifecycle_image_count" {
  description = "Maximum number of images retained by the repository lifecycle policy."
  type        = number
  default     = 20

  validation {
    condition     = var.ecr_lifecycle_image_count >= 1 && var.ecr_lifecycle_image_count <= 1000
    error_message = "ecr_lifecycle_image_count must be between 1 and 1000."
  }
}

variable "cloud_map_namespace_name" {
  description = "Private DNS namespace for stable Test Lab service discovery."
  type        = string
  default     = "dcc-test.internal"
}

variable "cloud_map_service_name" {
  description = "Cloud Map service name for the Test API."
  type        = string
  default     = "dcc-test-api"
}

variable "test_api_port" {
  description = "Test API container/listener port."
  type        = number
  default     = 8080

  validation {
    condition     = var.test_api_port >= 1 && var.test_api_port <= 65535
    error_message = "test_api_port must be a valid TCP port."
  }
}

variable "log_group_prefix" {
  description = "CloudWatch log-group ARN prefix for future ECS log groups; this foundation does not create log groups."
  type        = string
  default     = "/ecs/dcc-testlab"
}

variable "rds_identifier" {
  description = "Identifier for the private PostgreSQL Test Lab instance."
  type        = string
  default     = "dcc-testlab-postgres"
}

variable "rds_database_name" {
  description = "Initial PostgreSQL database name."
  type        = string
  default     = "dcctestlab"
}

variable "rds_master_username" {
  description = "Master username; AWS manages the generated password in Secrets Manager."
  type        = string
  default     = "dcc_testlab_admin"
}

variable "rds_instance_class" {
  description = "Lab-sized PostgreSQL instance class."
  type        = string
  default     = "db.t4g.micro"
}

variable "rds_allocated_storage_gb" {
  description = "Initial encrypted PostgreSQL storage in GiB."
  type        = number
  default     = 20
}

variable "redis_replication_group_id" {
  description = "Identifier for the single-node Redis-compatible Test Lab cache."
  type        = string
  default     = "dcc-testlab-redis"
}

variable "redis_node_type" {
  description = "Lab-sized ElastiCache Redis node type."
  type        = string
  default     = "cache.t4g.micro"
}

variable "test_app_image_digest" {
  description = "Immutable Test Lab application image digest deployed by both ECS services."
  type        = string
  default     = "sha256:8a620d72cd2824f75ed87bea3f9b3dff960dbbbe41a0ba2a50bb30f014294d40"

  validation {
    condition     = can(regex("^sha256:[0-9a-f]{64}$", var.test_app_image_digest))
    error_message = "test_app_image_digest must be a sha256 digest."
  }
}

variable "dcc_app_image_digest" {
  description = "Immutable DCC application image digest deployed by the DCC ECS service."
  type        = string
  default     = "sha256:a82d54d7b014f7643e29f0dc23762bab9033ca2cb05488907b0ecb708722b2fc"

  validation {
    condition     = can(regex("^sha256:[0-9a-f]{64}$", var.dcc_app_image_digest))
    error_message = "dcc_app_image_digest must be a sha256 digest."
  }
}

variable "common_tags" {
  description = "Additional non-sensitive tags applied to all managed resources."
  type        = map(string)
  default     = {}
}

variable "dcc_django_secret" {
  description = "Generated Django signing secret for the DCC ECS service; supplied out-of-band at apply time."
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.dcc_django_secret) >= 50
    error_message = "dcc_django_secret must contain at least 50 characters."
  }
}
