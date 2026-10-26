resource "aws_service_discovery_private_dns_namespace" "test_lab" {
  name        = var.cloud_map_namespace_name
  description = "Private service discovery namespace for the standalone DCC Test Lab."
  vpc         = aws_vpc.test_lab.id

  tags = {
    Name = "${var.name_prefix}-service-discovery"
  }
}

resource "aws_service_discovery_service" "test_api" {
  name = var.cloud_map_service_name

  dns_config {
    namespace_id   = aws_service_discovery_private_dns_namespace.test_lab.id
    routing_policy = "MULTIVALUE"

    dns_records {
      ttl  = 10
      type = "A"
    }
  }

  tags = {
    Name = "${var.name_prefix}-test-api-discovery"
  }
}
