resource "aws_db_subnet_group" "test_lab" {
  name       = "${var.rds_identifier}-subnets"
  subnet_ids = [for subnet in aws_subnet.private_data : subnet.id]

  tags = {
    Name = "${var.rds_identifier}-subnets"
  }
}

resource "aws_db_instance" "test_lab" {
  identifier                  = var.rds_identifier
  db_name                     = var.rds_database_name
  engine                      = "postgres"
  instance_class              = var.rds_instance_class
  allocated_storage           = var.rds_allocated_storage_gb
  storage_type                = "gp3"
  storage_encrypted           = true
  manage_master_user_password = true
  username                    = var.rds_master_username
  db_subnet_group_name        = aws_db_subnet_group.test_lab.name
  vpc_security_group_ids      = [aws_security_group.rds.id]
  publicly_accessible         = false
  multi_az                    = false
  backup_retention_period     = 1
  auto_minor_version_upgrade  = true
  deletion_protection         = false
  skip_final_snapshot         = true

  tags = {
    Name = var.rds_identifier
  }
}

resource "aws_elasticache_subnet_group" "test_lab" {
  name       = "${var.name_prefix}-redis-subnets"
  subnet_ids = [for subnet in aws_subnet.private_data : subnet.id]

  tags = {
    Name = "${var.name_prefix}-redis-subnets"
  }
}

resource "aws_elasticache_replication_group" "test_lab" {
  replication_group_id       = var.redis_replication_group_id
  description                = "Single-node private Redis-compatible cache for the DCC Test Lab."
  engine                     = "redis"
  node_type                  = var.redis_node_type
  num_cache_clusters         = 1
  automatic_failover_enabled = false
  multi_az_enabled           = false
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  subnet_group_name          = aws_elasticache_subnet_group.test_lab.name
  security_group_ids         = [aws_security_group.redis.id]
  port                       = 6379
  apply_immediately          = true

  tags = {
    Name = var.redis_replication_group_id
  }
}
