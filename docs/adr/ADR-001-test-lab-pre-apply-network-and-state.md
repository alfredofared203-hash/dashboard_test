# ADR-001: Test Lab Pre-Apply Network and State

- Status: Accepted for the pre-apply foundation; Task 38 supersedes the earlier DCC placement boundary
- Date: 2026-10-25
- Scope: Shared DCC/Test Lab network CIDRs, private security-group connectivity, and Terraform state configuration

## Decision

1. Retain the dedicated Test Lab VPC CIDR `10.80.0.0/16` from the approved network design. Use exactly two AZs and six subnets:

   | Tier | `eu-north-1a` | `eu-north-1b` |
   |---|---|---|
   | Public | `10.80.0.0/24` | `10.80.1.0/24` |
   | Private application | `10.80.16.0/20` | `10.80.32.0/20` |
   | Private data | `10.80.48.0/24` | `10.80.49.0/24` |

2. Reject Terraform plans whose subnet ranges fall outside the VPC or overlap one another. This validation does not prove non-overlap with external networks.
3. Place the DCC ECS service, Test API, Test Worker, and diagnostic tasks in the same dedicated VPC and private application subnets using `awsvpc` and no public task IP. The DCC runtime VPC will be created by the approved Test Lab/DCC deployment architecture.
4. Create a dedicated DCC control SG. Permit DCC-to-Test-API traffic only on the configured TCP API port, scoped by SG reference; keep DCC SG ingress empty. Do not use VPC peering, Transit Gateway, VPN, PrivateLink, or public connectivity between DCC and the Test Lab.
5. Provide a partial S3 remote-backend template in a separate, inactive Terraform directory with native S3 lockfiles (`use_lockfile = true`). Require Terraform `>= 1.10, < 2.0`; the existing AWS provider constraint remains `~> 6.0`, with `hashicorp/aws` `6.70.0` selected in the lockfile. Keep the template inactive so local-only planning remains possible until the backend bucket is approved.
6. Do not provision the state bucket in this stack or in AWS during this task. An approved external/bootstrap process must provide a dedicated versioned, encrypted, public-access-blocked S3 bucket and least-privilege access before controlled remote initialization.
7. Local inspection/planning may explicitly use `terraform init -backend=false`. Never treat local planning as production state. No existing managed-resource state was found; if one is later found, review and back it up before a separately approved state migration.

## Context

Task 36 found conflicting CIDR examples: the network design and Task 35 Terraform used `10.80.0.0/16`, while the older deployment blueprint used `10.42.0.0/16`. Task 36 also identified that external CIDR overlap had not been checked, DCC's network location and private path were not established, and the main Terraform stack had no remote backend or state locking.

Task 37 performed read-only AWS inspection in `eu-north-1`. Task 38 repeated the inspection: the configured identity can read one VPC, the default VPC `172.31.0.0/16` and its subnet ranges. Its route table contains the local VPC route and `0.0.0.0/0` to the attached IGW. No NAT gateways, VPC peering connections, Transit Gateway attachments, VPN gateways, or VPN connections were returned. `10.80.0.0/16` does not overlap those visible regional VPC/subnet ranges.

The DCC runtime VPC does not yet exist; **DCC runtime VPC: will be created by the approved Test Lab/DCC deployment architecture.** DCC-to-Test-Lab connectivity is same-VPC private task networking, not an external-VPC dependency. The Task 37 uncertainty was superseded by the explicit Task 38 architecture decision.

## Options considered

| Option | Decision |
|---|---|
| Keep the earlier Task 36 examples without change | Rejected: leaves conflicting CIDR instructions and no backend strategy. |
| Select an alternative VPC CIDR immediately | Rejected: no observed overlap requires changing the approved `10.80.0.0/16`; an alternative would be speculative. Revisit only if an external network overlap is confirmed. |
| Use public IPs, public tasks, or `0.0.0.0/0` API ingress to connect DCC | Rejected: violates the private Test API requirement and is unnecessary without knowing DCC's placement. |
| Put DCC in the Test Lab VPC | Selected by Task 38: both ECS services and diagnostic tasks use the same private application subnets/VPC. |
| Add VPC peering, Transit Gateway, VPN, or PrivateLink | Rejected for this architecture: all DCC-to-Test-Lab paths are within one VPC. |
| Keep the DCC SG and scoped API rule | Selected by Task 38: the DCC control SG lives in the dedicated VPC and allows only required same-VPC API egress; no inbound/public rule is added. |
| Continue with local Terraform state for deployment | Rejected: local state lacks the required shared access, protected storage, and remote lock coordination. |
| S3 backend with native S3 lockfile | Selected for future deployment: it supports remote state and locking without adding a DynamoDB lock table. The bucket is an external bootstrap dependency and is not created here. |

## Rationale

The `10.80.0.0/16` decision follows the already approved network-design document and existing Terraform defaults, rather than introducing a third CIDR. The six subnet defaults are distinct and inside the VPC; plan-time preconditions now enforce those properties if inputs change. The available AWS view shows no conflict with the only visible regional VPC.

The same-VPC decision is now explicit and represented in Terraform: DCC tasks use the private application subnet outputs and the DCC control SG; the Test API accepts its configured port from that SG. The diagnostic worker uses a separate SG for task-targeted requests. The RDS/Redis tiers remain private and unchanged.

Remote S3 state with native lockfiles is a supported Terraform/AWS option and avoids creating lock infrastructure inside the stack that depends on it. An externally provisioned bucket also separates bootstrap authority and lifecycle from the Test Lab resources. Keeping the backend declaration in an inactive template directory allows validation and read-only local planning without a pre-existing bucket. The existing provider release is pinned by the lockfile rather than upgraded speculatively.

## Consequences

- The authoritative CIDR example is now consistent across the design, deployment guide, Terraform defaults/example, and Terraform README. The former `10.42.0.0/16` deployment proposal is superseded historical context only.
- The approved regional AWS view shows no overlap with the planned VPC CIDR. The existing default VPC is not reused; the DCC runtime VPC will be created by the approved architecture.
- DCC-to-Test-API access is configured in the foundation with scoped SG references. The DCC ECS service itself, its task role, and operator ingress are not created by this foundation.
- The NAT Gateway remains one per the cost-conscious lab design; it is a single-AZ egress dependency and is not high availability.
- Task 37 removed an earlier placeholder DCC SG/rules while DCC placement was unresolved. Task 38 adds one DCC control SG, one Test API ingress rule, and two DCC egress rules to implement the now-approved same-VPC design.
- A remote plan requires an externally provisioned backend bucket with versioning, encryption, public access block, and tightly scoped IAM access. The backend template and example backend-values file contain no credentials and no real bucket.
- No Terraform bootstrap stack is added because the repository has no approved bootstrap convention and the bucket should be managed by an authorized platform process.
- Service counts, optional Prometheus/Loki/S3 telemetry, RDS/Redis resources, and DCC deployment remain separate future scope and approval items.

## Future dependencies

1. Provision and review the remote-state bucket outside this stack; initialize using the example backend config only after replacing its bucket placeholder.
2. Confirm deployment account, resource-creation permissions, quotas, NAT cost, and operational log/image-retention decisions.
3. Confirm DCC service placement uses the same private application subnets and `dcc_control` SG output; separately approve its operator-ingress path.
4. Regenerate and review a fresh plan immediately before any separately authorized apply.
