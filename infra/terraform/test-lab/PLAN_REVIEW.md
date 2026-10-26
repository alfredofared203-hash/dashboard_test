# Terraform Plan Review - DCC Test Laboratory

## Review result

**Historical pre-apply status (Task 38/39): NOT READY FOR APPLY.** This review was a read-only preparation record and did not authorize a deployment. Task 41 later authorized and completed the first lab apply; see [`APPLY_REPORT.md`](./APPLY_REPORT.md) for the actual result and verification.

The complete plan was generated from `infra/terraform/test-lab/` on 2026-10-25 using the configured AWS provider and `eu-north-1`. Terraform completed its read-only identity, partition, and available-AZ data lookups. The current plan is:

```text
Plan: 52 to add, 0 to change, 0 to destroy.
```

Compared with Task 37's 48-resource plan, four resources were added to implement Task 38's confirmed same-VPC design: one DCC control SG, one DCC-to-Test-API ingress rule, and two DCC egress rules (TCP 8080 to the Test API and HTTPS for AWS APIs). The plan contains only create actions and data-source reads. It does not contain ECS services/task definitions, RDS, ElastiCache, CloudWatch log groups, or public ingress resources.

At the time this review was written, no `terraform apply` or AWS write operation had been run. The plan was an observation at review time; Task 41 generated and inspected a fresh plan before applying it.

## Planned resource inventory

| Category | Count | Planned resources and purpose |
|---|---:|---|
| VPC and network | 7 | One dedicated VPC and six subnets: two public, two private application, and two private data subnets. |
| Routing | 11 | Three route tables, two default routes, and six subnet-to-route-table associations. Public subnets use an IGW route; application subnets use a NAT route; data subnets have only the implicit local VPC route. |
| NAT and Internet Gateway | 3 | One Internet Gateway, one Elastic IP, and one public NAT Gateway in public subnet index `0` (`eu-north-1a` in this plan). |
| Security groups and rules | 22 | Six DCC/workload/data security groups plus six ingress and ten egress rules, detailed below. |
| IAM | 5 | ECS task-trust roles for execution, API, worker, and diagnostic tasks, plus one inline execution-role policy. |
| ECR | 2 | One private shared API/worker image repository and one lifecycle policy retaining up to the configured image count. |
| Cloud Map | 2 | One private DNS namespace associated with the new VPC and one Test API service definition. |
| Other supporting resources | 0 | The availability-zone, caller-identity, partition, and IAM-policy-document data sources are reads, not created infrastructure resources. |
| **Total** | **52** | **52 creates, 0 changes, 0 destroys.** |

### Network and routing review

- The plan defines a dedicated VPC with CIDR `10.80.0.0/16`; VPC DNS support and DNS hostnames are enabled in the Terraform resource.
- The two AZs selected by this plan are `eu-north-1a` and `eu-north-1b`. The default implementation selects the first two available AZ names unless two names are explicitly configured.
- The six planned subnet CIDRs match the design defaults:

  | Tier | AZ `eu-north-1a` | AZ `eu-north-1b` | Intended use |
  |---|---|---|---|
  | Public | `10.80.0.0/24` | `10.80.1.0/24` | NAT egress and reserved public-tier infrastructure only |
  | Private application | `10.80.16.0/20` | `10.80.32.0/20` | DCC, ECS/Fargate API, worker, and diagnostic tasks |
  | Private data | `10.80.48.0/24` | `10.80.49.0/24` | Future RDS and ElastiCache subnet groups |

- No ECS, RDS, or ElastiCache resources are in this plan, so their subnet placement is an intended future use, not an already-enforced service configuration.
- Public subnets associate with a route table whose `0.0.0.0/0` route targets the IGW. The NAT Gateway uses the first public subnet.
- Both private application subnets associate with one private application route table. When `enable_nat_gateway = true`, its `0.0.0.0/0` route targets the NAT Gateway, not the IGW.
- Both private data subnets associate with a separate route table. No Internet or NAT default route is declared for that table; VPC-local routing remains available.
- All subnet resources set `map_public_ip_on_launch = false`. No planned private subnet has a direct IGW route, and no planned workload has a public IP assignment. **The plan contains no route that directly exposes a private workload to the Internet.**
- Terraform preconditions verify that all six subnet CIDRs fit inside `10.80.0.0/16` and do not overlap one another. They cannot verify overlap with external routes.
- The public route itself is intentional. A future workload deliberately placed in a public subnet and assigned a public address would have an Internet route; future deployment configuration must keep application/data workloads in their private tiers.

### NAT and cost review

One public NAT Gateway and one associated Elastic IP are planned in the first public subnet (`eu-north-1a`). The single private application route table used by both private application subnets sends default outbound traffic through this NAT. Private data subnets do not depend on it.

This matches the approved cost-conscious initial design. It creates a single egress dependency and an AZ failure/cross-AZ traffic risk for workloads in the other AZ; it is **not** equivalent to a production-grade multi-AZ HA design. NAT Gateway hourly and data-processing charges, plus the public IPv4 address charge where applicable, must be checked against current regional pricing and approved before deployment. Do not add a second NAT Gateway as part of this review.

If `enable_nat_gateway` is set to `false`, the plan will omit the NAT, EIP, and private application default route; private application workloads then have no default Internet egress through this design. That option is not the setting used for this reviewed plan.

### Security group review

All six SGs are created in the dedicated VPC. Their inline ingress and egress lists are empty; the following explicit standalone rules are planned. There are no all-protocol/all-port rules.

| Source | Destination | Port | Protocol | Direction | Purpose |
|---|---|---:|---|---|---|
| DCC control SG | Test API SG | 8080 | TCP | Ingress to Test API / egress from DCC | Private DCC-to-Test-API traffic |
| Diagnostic worker SG | Test API SG | 8080 | TCP | Ingress to Test API / egress from diagnostic worker | Diagnostic worker to selected Test API task |
| Test API SG | RDS SG | 5432 | TCP | Ingress to RDS / egress from Test API | PostgreSQL client traffic |
| Test worker SG | RDS SG | 5432 | TCP | Ingress to RDS / egress from Test Worker | PostgreSQL client traffic |
| Test API SG | Redis SG | 6379 | TCP | Ingress to Redis / egress from Test API | Redis/Valkey client traffic |
| Test worker SG | Redis SG | 6379 | TCP | Ingress to Redis / egress from Test Worker | Redis/Valkey client traffic |

The plan also adds outbound rules:

| Source | Destination | Port | Protocol | Direction | Purpose |
|---|---|---:|---|---|---|
| DCC control, diagnostic worker, Test API, Test worker SGs | `0.0.0.0/0` | 443 | TCP | Egress only | HTTPS egress for AWS APIs, image/log bootstrap, and approved external endpoints; routed through NAT for private application subnets |
| DCC control SG | Test API SG | 8080 | TCP | Egress from DCC | Private DCC-to-Test-API client traffic |
| Diagnostic worker SG | Test API SG | 8080 | TCP | Egress from diagnostic worker | Diagnostic client traffic |
| Test API SG | RDS SG | 5432 | TCP | Egress from Test API | PostgreSQL client traffic |
| Test API SG | Redis SG | 6379 | TCP | Egress from Test API | Redis/Valkey client traffic |
| Test worker SG | RDS SG | 5432 | TCP | Egress from Test Worker | PostgreSQL client traffic |
| Test worker SG | Redis SG | 6379 | TCP | Egress from Test Worker | Redis/Valkey client traffic |

PostgreSQL and Redis/Valkey ingress are restricted to the respective API/worker SG references; neither accepts `0.0.0.0/0`. API ingress is scoped to the DCC control and diagnostic-worker SGs. DCC SG ingress is empty. No public inbound rule, broad internal ingress, or all-to-all SG relationship is planned. Security groups are stateful, so response traffic for permitted connections does not require reciprocal inbound rules. Metrics-scrape rules are not part of this foundation.

The four HTTPS egress rules to `0.0.0.0/0` are destination-broad even though limited to TCP 443. Security groups cannot enforce domain-name allowlists. For stronger egress control, separately design VPC endpoints and/or an approved egress proxy/filtering policy before deployment. These rules do not create Internet ingress.

### IAM, ECR, and Cloud Map review

- The execution role trust is limited to `ecs-tasks.amazonaws.com`. Its policy permits `ecr:GetAuthorizationToken` on `*` (required by AWS for that action), image pull actions on the one planned repository, and CloudWatch log stream/event writes under the configured `/ecs/dcc-testlab/*` log-group prefix.
- The policy does not grant `logs:CreateLogGroup`. Log groups therefore need to be provisioned separately before task logging can use this policy. API, worker, and diagnostic task roles have no application permissions attached.
- No DCC control-plane role, ECS `RunTask`/`StopTask`, `iam:PassRole`, secret retrieval, or database credential permissions are included. They require a separate least-privilege review when task definitions and secret identifiers are known.
- The ECR repository is private by default, uses AES256 encryption, immutable tags, push scanning, and a lifecycle policy limited to the newest configured image count. Lifecycle expiry can remove old deployment/rollback images; verify retention requirements before relying on it.
- Cloud Map creates a private DNS namespace and an A-record service definition in the new VPC. It does not create an ECS service, register tasks, or itself provide a path from the separately deployed DCC service.

## Task 38 final validation status

**Final approval state: NOT READY FOR CONTROLLED APPLY**

| Gate | Status | Task 38 result / remaining dependency |
|---|---|---|
| Conflicting CIDR documentation | **RESOLVED** | `10.80.0.0/16` and the same six subnets are authoritative in Terraform, the network design, deployment guide, README, and ADR-001. The prior alternative is preserved only as explicitly superseded historical context in the ADR/design note. |
| Network topology and CIDR validation | **PASS** | The plan creates one VPC, two AZs, six unique subnets, one IGW, one NAT, and separate public/app/data route tables. VPC DNS support/hostnames are enabled; app routes use NAT; data routes have no Internet/NAT default; all subnet map-public-IP settings are false. The valid `10.80.0.0/16` plan succeeds; overlapping and out-of-VPC subnet inputs fail at Terraform preconditions. |
| AWS-visible CIDR overlap | **PASS FOR THIS ARCHITECTURE** | Read-only `eu-north-1` inventory showed only the existing default VPC `172.31.0.0/16` and its subnets; its main route table has a local route and an IGW default route. No NAT, peering, Transit Gateway attachment, VPN gateway, VPN connection, or Client VPN endpoint was returned. The planned `10.80.0.0/16` does not overlap the visible AWS network. DCC and Test Lab share the new VPC, so no separate-VPC connectivity dependency exists. |
| DCC and Test Lab same-VPC placement | **RESOLVED IN DESIGN / FOUNDATION** | Task 38 sets the DCC ECS service, Test API, Test Worker, and diagnostic tasks in the same dedicated VPC and private application subnets. Terraform creates the DCC control SG, scoped TCP `test_api_port` egress to the Test API SG, and matching API ingress. No cross-VPC path or public IP is required. The foundation does not create ECS services/task definitions. |
| Remote state/backend/locking | **BLOCKED — EXTERNAL DEPENDENCY** | The repository includes an inactive S3 backend template at `backend-template/backend.tf` using native lockfiles and a non-secret backend-value example. Terraform `>= 1.10` is required. No state bucket is provisioned; an authorized external/bootstrap process must provide a versioned, encrypted, public-access-blocked bucket and scoped access before enabling the backend in the stack root. No bootstrap stack is created. |
| Account, quotas, permissions, and cost approval | **BLOCKED — EXTERNAL DEPENDENCY** | Task 39 created `COST_REVIEW.md` and `APPLY_RUNBOOK.md`, and confirmed selected read-only quota values. Effective resource-creation permissions, all relevant quota headroom, and explicit cost approval remain unverified/not confirmed. |
| Logs and image retention dependencies | **DEFERRED — NOT REQUIRED FOR FOUNDATION** | The plan creates no ECS tasks or log groups. Before task deployment, decide retention, provision required log groups, and verify lifecycle retention against rollback needs. |
| Fresh review immediately before any apply | **DEFERRED — NOT REQUIRED FOR FOUNDATION** | This plan is a dated snapshot. A fresh plan and separate apply approval are mandatory at a later deployment stage. |
| Historical Task 33 report provenance | **DEFERRED — NOT REQUIRED FOR FOUNDATION** | The original report remains absent from the workspace. Task 37 performed a new read-only regional VPC/subnet/peering/TGW inventory, but it does not reconstruct unrelated historical Task 33 findings. |

The network foundation matches the dedicated two-AZ/six-subnet layout and supports DCC/Test Lab workloads in one VPC. The current status is recorded in [`FINAL_PRE_APPLY_REPORT.md`](./FINAL_PRE_APPLY_REPORT.md): **NOT READY FOR CONTROLLED AWS APPLY** until the blocked external prerequisites are resolved and a fresh plan is reviewed.

## Validation performed

- `terraform fmt -recursive` and `terraform fmt -check -recursive`: passed for the Task 38 Terraform edits, including the backend template directory.
- `terraform validate`: passed for the Test Lab stack.
- `terraform init -backend=false` and `terraform validate`: passed in `backend-template/`; no backend bucket access was attempted.
- `terraform plan -input=false -no-color`: succeeded after Task 38 changes; 52 to add, 0 to change, 0 to destroy. No destroy or replacement (`-/+`) action was found in the inspected plan.
- Default valid CIDRs passed a read-only plan. Negative plan checks with intentionally overlapping and out-of-VPC subnet inputs both stopped at the VPC resource precondition, confirming invalid subnet layouts are rejected before apply.
- Plan search for `public` and `0.0.0.0/0`: the public route is the intended public-subnet IGW default route; the private-application route targets the NAT Gateway; HTTPS `0.0.0.0/0` matches outbound TCP 443 SG rules only. Public IP attributes belong to the NAT EIP/NAT; all six subnets set `map_public_ip_on_launch = false`. No public workload/API IP or public ingress SG rule is planned.
- AWS identity and regional VPC/subnet/route-table/IGW/NAT/peering/Transit Gateway/VPN/Client VPN/ECS cluster reads: succeeded in `eu-north-1`; one existing default VPC `172.31.0.0/16` with public-routed subnets was visible, with no NAT, peering, TGW attachment, VPN gateway, VPN connection, Client VPN endpoint, or ECS cluster. The proposed `10.80.0.0/16` does not overlap the visible AWS network. **DCC runtime VPC: will be created by the approved Test Lab/DCC deployment architecture.** It is not an external-VPC dependency. No writes were performed.
- Terraform state/plan artifact scan: no `*.tfstate`, `*.tfplan`, or related files found in the workspace outside generated `.terraform` metadata and ignored dependency/build directories. The workspace is not a Git working tree, so tracked/committed-state history could not be verified. `.gitignore` now covers state, saved plan files, `terraform.tfvars`, and generated `backend.hcl`, while allowing the examples.
- Earlier application validation (Task 37): `manage.py check` and `manage.py test` passed; 137 DCC tests passed. The requested `pytest` invocation was attempted but `pytest` is not installed in the DCC virtual environment. Frontend typecheck/build passed; Test Lab pytest passed (22 tests, one upstream deprecation warning).
- No `terraform apply`, AWS resource write, or deployment was performed.

The plan file was reviewed locally from the command output and is not checked in; this document records its summarized inventory and findings rather than persisting provider output or account-specific details.
