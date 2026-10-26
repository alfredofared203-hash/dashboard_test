locals {
  availability_zones = length(var.availability_zones) == 2 ? var.availability_zones : try(slice(data.aws_availability_zones.available.names, 0, 2), [])

  base_tags = merge(var.common_tags, {
    Project     = var.project_name
    Environment = var.environment_name
    ManagedBy   = "IaC"
    Purpose     = "standalone-test-laboratory"
  })

  public_subnets = {
    for index, az in local.availability_zones : tostring(index) => {
      az   = az
      cidr = var.public_subnet_cidrs[index]
    }
  }

  private_application_subnets = {
    for index, az in local.availability_zones : tostring(index) => {
      az   = az
      cidr = var.private_application_subnet_cidrs[index]
    }
  }

  private_data_subnets = {
    for index, az in local.availability_zones : tostring(index) => {
      az   = az
      cidr = var.private_data_subnet_cidrs[index]
    }
  }

  subnet_cidrs = concat(
    var.public_subnet_cidrs,
    var.private_application_subnet_cidrs,
    var.private_data_subnet_cidrs,
  )

  ipv4_ranges = {
    for index, cidr in concat([var.vpc_cidr], local.subnet_cidrs) : tostring(index) => {
      start = sum([
        for octet_index, octet in split(".", cidrhost(cidr, 0)) :
        tonumber(octet) * pow(256, 3 - octet_index)
      ])
      end = sum([
        for octet_index, octet in split(".", cidrhost(cidr, -1)) :
        tonumber(octet) * pow(256, 3 - octet_index)
      ])
    }
  }

  subnet_cidrs_within_vpc = alltrue([
    for index in range(length(local.subnet_cidrs)) :
    local.ipv4_ranges[tostring(index + 1)].start >= local.ipv4_ranges["0"].start &&
    local.ipv4_ranges[tostring(index + 1)].end <= local.ipv4_ranges["0"].end
  ])

  subnet_cidrs_are_non_overlapping = alltrue(flatten([
    for index in range(length(local.subnet_cidrs)) : [
      for other_index in range(length(local.subnet_cidrs)) :
      index >= other_index ? true : (
        local.ipv4_ranges[tostring(index + 1)].start > local.ipv4_ranges[tostring(other_index + 1)].end ||
        local.ipv4_ranges[tostring(other_index + 1)].start > local.ipv4_ranges[tostring(index + 1)].end
      )
    ]
  ]))
}

check "two_available_availability_zones" {
  assert {
    condition     = length(local.availability_zones) == 2
    error_message = "The Test Lab requires exactly two available Availability Zones."
  }
}

check "configured_availability_zones_are_available" {
  assert {
    condition     = alltrue([for az in local.availability_zones : contains(data.aws_availability_zones.available.names, az)])
    error_message = "Every configured availability_zones entry must be available in aws_region."
  }
}
