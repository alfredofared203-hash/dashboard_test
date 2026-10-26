resource "aws_vpc" "test_lab" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  lifecycle {
    precondition {
      condition     = local.subnet_cidrs_within_vpc
      error_message = "Every public, private-application, and private-data subnet CIDR must fit inside vpc_cidr."
    }

    precondition {
      condition     = local.subnet_cidrs_are_non_overlapping
      error_message = "Public, private-application, and private-data subnet CIDRs must not overlap."
    }
  }

  tags = {
    Name = "${var.name_prefix}-vpc"
  }
}

resource "aws_subnet" "public" {
  for_each = local.public_subnets

  vpc_id                  = aws_vpc.test_lab.id
  availability_zone       = each.value.az
  cidr_block              = each.value.cidr
  map_public_ip_on_launch = false

  tags = {
    Name = "${var.name_prefix}-public-${each.value.az}"
    Tier = "public"
  }
}

resource "aws_subnet" "private_application" {
  for_each = local.private_application_subnets

  vpc_id                  = aws_vpc.test_lab.id
  availability_zone       = each.value.az
  cidr_block              = each.value.cidr
  map_public_ip_on_launch = false

  tags = {
    Name = "${var.name_prefix}-private-app-${each.value.az}"
    Tier = "private-application"
  }
}

resource "aws_subnet" "private_data" {
  for_each = local.private_data_subnets

  vpc_id                  = aws_vpc.test_lab.id
  availability_zone       = each.value.az
  cidr_block              = each.value.cidr
  map_public_ip_on_launch = false

  tags = {
    Name = "${var.name_prefix}-private-data-${each.value.az}"
    Tier = "private-data"
  }
}

resource "aws_internet_gateway" "test_lab" {
  vpc_id = aws_vpc.test_lab.id

  tags = {
    Name = "${var.name_prefix}-igw"
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.test_lab.id

  tags = {
    Name = "${var.name_prefix}-rt-public"
  }
}

resource "aws_route" "public_default" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.test_lab.id
}

resource "aws_route_table_association" "public" {
  for_each = aws_subnet.public

  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}

resource "aws_eip" "nat" {
  count = var.enable_nat_gateway ? 1 : 0

  domain = "vpc"

  tags = {
    Name = "${var.name_prefix}-nat-eip"
  }
}

resource "aws_nat_gateway" "test_lab" {
  count = var.enable_nat_gateway ? 1 : 0

  allocation_id = aws_eip.nat[0].id
  subnet_id     = aws_subnet.public["0"].id

  depends_on = [
    aws_internet_gateway.test_lab,
    aws_route_table_association.public,
  ]

  tags = {
    Name = "${var.name_prefix}-nat"
  }
}

resource "aws_route_table" "private_application" {
  vpc_id = aws_vpc.test_lab.id

  tags = {
    Name = "${var.name_prefix}-rt-private-app"
  }
}

resource "aws_route" "private_application_default" {
  count = var.enable_nat_gateway ? 1 : 0

  route_table_id         = aws_route_table.private_application.id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.test_lab[0].id
}

resource "aws_route_table_association" "private_application" {
  for_each = aws_subnet.private_application

  subnet_id      = each.value.id
  route_table_id = aws_route_table.private_application.id
}

resource "aws_route_table" "private_data" {
  vpc_id = aws_vpc.test_lab.id

  tags = {
    Name = "${var.name_prefix}-rt-private-data"
  }
}

resource "aws_route_table_association" "private_data" {
  for_each = aws_subnet.private_data

  subnet_id      = each.value.id
  route_table_id = aws_route_table.private_data.id
}
