# DCC Test Laboratory Terraform Foundation

## Purpose and safety boundary

This directory defines the DCC/Test Lab foundation and private data-layer configuration in one dedicated VPC in AWS `eu-north-1`. The network foundation is deployed; the RDS and Redis-compatible resources described below are configured for a separately reviewed deployment plan.

Terraform configuration and a Terraform plan do not themselves deploy resources. Apply only a freshly reviewed plan under the task's deployment authorization; do not infer apply authorization from this README.

The foundation currently defines:

- dedicated VPC, two AZs, six subnets, IGW, one optional NAT Gateway, and route tables;
- dedicated DCC/Test Lab SGs and narrowly scoped workload/data port rules;
- private encrypted PostgreSQL RDS and single-node encrypted Redis-compatible ElastiCache definitions, using the private data subnet tier and existing SGs;
- ECR repository for the shared Test Lab API/worker image and a dedicated immutable DCC application repository;
- ECS task execution, API task, worker task, and diagnostic task IAM role structures;
- a private Cloud Map namespace and Test API service-discovery record definition.

ECS cluster/services/task definitions, log groups, Container Insights, Prometheus, Loki, ALB, and DCC service deployment are deliberately deferred.

## Reconciliation status

The requested source `docs/aws-test-lab-network-preflight.md` is absent from the repository. Task 33 findings used here were previously recorded from read-only AWS CLI inspection and are summarized in [`docs/aws-test-lab-network-design.md`](../../../docs/aws-test-lab-network-design.md). They are not independently verified from a checked-in Task 33 report.

The network design retains the observed facts: one unsuitable default VPC, three public-routed subnets in three AZs, IGW, no NAT/private tier, default SG only, and no ECS/ECR/RDS/ElastiCache resources in the inspected region. Fargate, RDS, and ElastiCache APIs were accessible.

Task 34’s design chooses a **dedicated VPC**, two AZs, six subnets, private app/data tiers, one initial NAT Gateway, Cloud Map, and `10.80.0.0/16`. Task 37 confirms that this is the authoritative repository layout and records it in [`docs/adr/ADR-001-test-lab-pre-apply-network-and-state.md`](../../../docs/adr/ADR-001-test-lab-pre-apply-network-and-state.md). Task 38 rechecked the regional inventory: the CIDR does not overlap any visible VPC/subnet. DCC and Test Lab tasks will use this same VPC, so no separate-VPC DCC network dependency applies.

The earlier [`docs/deployment/aws-test-lab.md`](../../../docs/deployment/aws-test-lab.md) proposal used a different CIDR. Task 37 updated its example to the authoritative allocation while preserving the historical alternative in the ADR. Task 38 establishes that the DCC ECS service, Test API, and Test Worker will use this same VPC and private application subnets; it adds a DCC control SG and a private TCP rule to the Test API. DCC ECS service/task deployment itself remains outside this foundation.

Why this foundation keeps the approved direction:

- **Dedicated VPC/private app and data subnets:** isolates the lab and keeps Fargate tasks, PostgreSQL, and Redis off public IPs.
- **Two AZs:** enough for initial ECS placement and future multi-AZ subnet groups; third AZ can be added in a later reviewed change.
- **One NAT Gateway:** the approved cost-conscious starting point. It is not AZ resilient; private application traffic has one egress dependency. NAT can be disabled, in which case private tasks have no internet egress.
- **Cloud Map:** supplies a stable private service-level Test API DNS name. Target-specific diagnostics still resolve the selected live ECS task’s current private IP from ECS because task IPs are transient.
- **Separate ECR repositories:** API and worker modes share the Test Lab image repository; the DCC application uses its own `dcc-app` repository.

## Architecture

```text
eu-north-1
└── Dedicated dcc-testlab VPC (10.80.0.0/16)
    ├── AZ-a: public / private-app / private-data
    └── AZ-b: public / private-app / private-data
        ├── IGW -> public route table
        ├── one NAT -> private-app route table (optional)
        └── private-data route table (local VPC route only)

Future private ECS API/worker/diagnostic tasks
  ├── DCC ECS service: same private application subnets/VPC
  ├── API service DNS: dcc-test-api.dcc-test.internal
  ├── task-specific diagnostic target: fresh ECS task ENI private IP
  ├── private PostgreSQL: TCP 5432 from API/worker SGs
  └── private Redis-compatible cache: TCP 6379 from API/worker SGs
```

The DCC ECS service, Test API, Test Worker, and diagnostic tasks are intended to use this VPC's private application subnets with `awsvpc` and public IP assignment disabled. DCC's SG can reach the Test API on its configured TCP port; the DCC service can use the same VPC's private DNS and task private IPs. PostgreSQL and Redis are configured for the private data subnets and use their existing SGs, with access scoped to Test API/worker SGs. The stack does not create ECS services or their task definitions. No cross-VPC mechanism or public path is part of this design.

The current files create no ECS services; data-store subnet groups and instances are defined separately in `data_services.tf`. Security groups include only the intended SG-to-SG rules, plus TCP 443 outbound from app tasks to support image startup/logging/AWS HTTPS APIs through the NAT. Such internet egress is destination-broad; SG rules cannot filter by DNS name. Prefer VPC endpoints and/or an approved egress control design if the deployment requires destination allowlisting.

## Directory structure

| File | Responsibility |
|---|---|
| `versions.tf` | Terraform and AWS provider version constraints |
| `backend-template/backend.tf`, `backend.s3.example.hcl` | Partial S3 remote-state configuration and safe non-secret example backend values |
| `providers.tf` | AWS provider using standard credential chain; region/AZ/account data sources |
| `variables.tf` | Region, CIDRs, AZs, NAT, naming, ports, Cloud Map, tags |
| `locals.tf` | Two-AZ selection, subnet maps, required tags, CIDR validation values |
| `network.tf` | VPC, six subnets, IGW, NAT/EIP, and routing |
| `security_groups.tf` | DCC, diagnostic, API, worker, and data SGs with explicit private rules |
| `data_services.tf` | Private PostgreSQL RDS and single-node Redis-compatible ElastiCache with private subnet groups |
| `iam.tf` | ECS trust roles and scoped execution policy; empty task-role permissions |
| `ecr.tf` | Immutable Test Lab and DCC application repositories; Test Lab image lifecycle policy |
| `service_discovery.tf` | Private Cloud Map namespace and Test API service |
| `outputs.tf` | Non-secret network/resource identifiers and ARNs |
| `terraform.tfvars.example` | Safe sample configuration, not secrets |
| `BACKEND_BOOTSTRAP.md` | Remote-state bucket requirements, initialization, locking, and recovery |
| `COST_REVIEW.md` | Cost drivers for resources present in the plan |
| `APPLY_RUNBOOK.md` | Controlled operator sequence for a future first deployment |
| `FINAL_PRE_APPLY_REPORT.md` | Task 39 validation evidence and final readiness status |
| `APPLY_REPORT.md` | Task 41 first apply result and read-only AWS verification |

## Prerequisites and authentication

- Terraform `>= 1.10, < 2.0`; 1.10 is required for native S3 lockfiles (`use_lockfile`).
- AWS CLI/credential chain configured by the operator, or an approved assumed role/task role.
- Read access to the configured region for `aws_availability_zones`, partition, and account identity data sources.
- Provider registry access for `terraform init`.
- Before any future apply: reviewed account/region, CIDR-overlap check, quota/cost approvals, and resource-creation IAM grants.

The AWS provider uses Terraform’s standard AWS credential chain. **Do not put access keys in `.tf`, `.tfvars`, environment files committed to the repository, provider blocks, outputs, or state.** Terraform state can contain sensitive infrastructure details; protect it and do not commit it.

## Variables

Defaults are in `variables.tf`; a copyable sample is in `terraform.tfvars.example`.

| Variable | Default / purpose |
|---|---|
| `aws_region` | `eu-north-1` |
| `project_name`, `environment_name`, `name_prefix` | Required ownership/resource naming labels |
| `vpc_cidr` | Authoritative `10.80.0.0/16`; checked against the AWS-visible regional VPC inventory; DCC uses this same VPC |
| `availability_zones` | Two AZ names; empty derives first two available AZ names |
| `public_subnet_cidrs` | `10.80.0.0/24`, `10.80.1.0/24` |
| `private_application_subnet_cidrs` | `10.80.16.0/20`, `10.80.32.0/20` |
| `private_data_subnet_cidrs` | `10.80.48.0/24`, `10.80.49.0/24` |
| `enable_nat_gateway` | `true`; one NAT. `false` removes NAT/default app route |
| `ecr_repository_name` | One shared API/worker image repo |
| `ecr_lifecycle_image_count` | Retain the newest 20 images |
| `cloud_map_namespace_name`, `cloud_map_service_name` | Private service-discovery DNS |
| `test_api_port` | 8080; DCC control and diagnostic-worker access from their dedicated SGs |
| `log_group_prefix` | Policy ARN scope only; log groups are not created here |
| `rds_*` | Lab PostgreSQL identifier, database, managed master username, instance class, and storage size |
| `redis_*` | Single-node ElastiCache replication-group ID and node type |
| `common_tags` | Additional non-sensitive tags |

Subnet CIDRs are explicit lists, aligned by index with the two AZs. Terraform preconditions reject ranges outside the VPC and overlapping subnet CIDRs. The approved DCC/Test Lab design has no separate VPC connection; any future change to connect another network requires its own overlap review.

## Initialization, formatting, validation, and planning

Run commands from this directory:

```powershell
Copy-Item terraform.tfvars.example terraform.tfvars
# Review non-secret values. Without backend.tf, Terraform initializes local-only planning.
terraform init
terraform fmt -check -recursive
terraform validate
terraform plan -input=false
```

`terraform init` downloads providers and creates local Terraform metadata/lock files. With no active `backend.tf`, Terraform uses local state for planning; this does not create AWS infrastructure. `terraform plan` performs read-only AWS data lookups and computes a proposed change set. A plan must be reviewed and is **not** approval to apply.

### Remote state and bootstrap

The checked-in `backend-template/backend.tf` is a partial S3 backend declaration using native S3 lockfiles. It lives in a separate template directory and is intentionally not loaded by the main stack, so normal local planning remains possible. No state bucket, lock resource, or bootstrap stack is created here. Before a real deployment, an authorized platform/operator process must provision an existing dedicated state bucket with versioning enabled, encryption, public-access blocking, and narrowly scoped access. Do not store state in this application stack's resource graph.

For a controlled remote initialization, copy `backend-template\backend.tf` to the stack root as `backend.tf`, copy `backend.s3.example.hcl` to the ignored `backend.hcl`, replace the bucket placeholder with the approved bucket name, then run:

```powershell
terraform init -reconfigure -backend-config=backend.hcl
```

Do not put credentials in either backend file; the AWS provider/backend use the standard credential chain. The backend config may disclose internal bucket/key names, so the generated `backend.hcl` is ignored. Keep both example files credential-free. Add root `backend.tf` only as part of an approved deployment configuration change.

Local-only planning creates no managed AWS resources or remote state. Because no Terraform resource state has been created by this foundation, there is currently no resource state to migrate. If a future local state contains managed resources, stop and review it, make a protected backup, verify the destination bucket/access/locking, and use Terraform's documented `terraform init -migrate-state -backend-config=backend.hcl` procedure only under a separate approved change instead of `-reconfigure`. Confirm the migration result and remote lock behavior before any apply. The backend bucket's own provisioning/ownership is a bootstrap dependency; no bootstrap Terraform code or convention exists in this repository.

**Do not run `terraform apply` as part of this task.** It would create or modify AWS infrastructure and is prohibited here. No apply or AWS write command is authorized by this foundation.

Terraform-specific generated and private files are ignored by the repository `.gitignore`: `.terraform/`, state files, saved plans, generated backend config, and user `*.tfvars`. `terraform.tfvars.example` and `backend.s3.example.hcl` remain source controlled. The provider constraint is `~> 6.0`; `.terraform.lock.hcl` currently pins `hashicorp/aws` `6.70.0`. Keep the lockfile committed to preserve the tested provider selection; do not upgrade it without a separate review.

## IAM and security notes

- Execution role: ECR pull permissions scoped to the one repository, CloudWatch log stream/event writes scoped below the configured future log-group prefix, and `ecr:GetAuthorizationToken` on `*` because AWS requires that action’s resource scope.
- API, worker, and diagnostic task roles have no application permissions attached yet.
- No DCC control-plane role, `RunTask`/`StopTask`, `iam:PassRole`, ECS service role, Secrets Manager access, or database credentials are defined here. Those require separate reviewed, resource-scoped policy work after ECS task definitions and secret identifiers are finalized.
- SGs have no public inbound access. PostgreSQL and Redis accept only from the Test API/worker SGs. API 8080 accepts only the DCC control and diagnostic-worker SGs. DCC's SG allows outbound HTTPS for AWS APIs and TCP 8080 to the Test API; it has no inbound rule. DCC, API, worker, and diagnostic tasks are intended for the same private application subnets/VPC.
- The `0.0.0.0/0` egress on HTTPS from application/diagnostic tasks is outbound only, through NAT for private application subnets. It is destination-broad and does not provide public inbound. Replace or narrow it if endpoints/egress controls are adopted.

## Future deployment phases

1. Confirm `10.80.0.0/16` remains the approved VPC CIDR and matches the current region/account inputs.
2. Review and approve Terraform foundation, AWS permissions, provider lock, remote state bucket/locking, and cost.
3. Review the Task 43 data-layer plan, then deploy PostgreSQL and Redis/Valkey using the private data subnet groups.
4. Add CloudWatch log groups/retention and finalize execution-role scopes/secrets injection.
5. Add ECS cluster, API/worker task definitions/services, health checks, and Cloud Map registration.
6. Deploy the DCC ECS service in the same VPC/private application subnets using the `dcc_control` SG output; separately review its service ingress and ECS task role permissions.
7. Validate direct task-IP targeting, stale-IP refresh, safety guardrails, and stop cleanup.
8. Add Prometheus/Loki only after ownership, endpoint, retention, cost, and network requirements are approved.

None of these deployment phases is performed by this foundation task.

## Cost and cleanup

The VPC, route tables, SGs, Cloud Map, IAM roles, and ECR repository have different billing characteristics; NAT Gateway is the dominant fixed network cost in this design. Fargate, ECR storage/scanning, CloudWatch logs, and data services add usage-based costs. Current eu-north-1 pricing and required quotas must be checked before deployment.

Future teardown must remove ECS services/tasks before Cloud Map and SG references; data stores require an explicit retention/snapshot decision; ECR images and repositories require lifecycle review; NAT Gateway and its EIP must be released before removing public routes/subnets/VPC. Never destroy or repurpose the observed default VPC as part of this lab teardown.

## Current status

The Task 41 foundation and Task 44 private PostgreSQL/Redis data layer were applied and verified read-only. Task 43 reconciled SG ownership and prepared the exact four-resource data-layer plan. See [`APPLY_REPORT.md`](./APPLY_REPORT.md) for the plan, apply counts, endpoints, and verification results. No ECS services, CloudWatch log groups, or applications have been deployed. Terraform state is local in this working copy and must be preserved for subsequent Terraform operations.
