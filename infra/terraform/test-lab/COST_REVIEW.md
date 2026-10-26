# Test Lab Terraform Cost Review

## Scope

This review covers only resources present in the current Test Lab Terraform plan: **52 to add, 0 to change, 0 to destroy**. It does not estimate prices. All prices, taxes, data-transfer rates, and regional product availability require verification against current AWS pricing for `eu-north-1` **before apply**.

The stack currently creates no ECS clusters/services/task definitions, RDS instances, ElastiCache resources, CloudWatch log groups, or application metrics. Future runtime cost for those products is described only to make clear that it is outside this plan.

## Planned resource costs

| Resource/category in this plan | Billable? / main cost driver | Baseline behavior | Cost controls that preserve the architecture |
|---|---|---|---|
| NAT Gateway (one) | **Yes; meaningful recurring lab cost.** Hourly gateway charge plus data processing; cross-AZ app egress through the single gateway may also incur transfer charges. | Recurs while provisioned, even when tasks are idle. This design routes both private application subnets through the NAT. | Retain exactly one NAT as approved; schedule/deploy the lab only when needed and remove it only through a separately approved teardown. Validate required egress before deployment. Do not replace it with public tasks or a public API. |
| Elastic IP for NAT (one) | **Potentially billable** as a public IPv4 address; verify the current public IPv4 pricing and allocation rules before apply. | Associated with the NAT and retained while that NAT exists. | Keep only the single planned NAT/EIP; release both through approved teardown when the lab is decommissioned. |
| VPC, subnets, route tables, routes, IGW | VPC/subnets/routes/route tables/IGW have no separate hourly charge under normal AWS pricing; data transfer, public IPv4, or attached billable services can still incur charges. **Verify before apply.** | Mostly non-recurring configuration; routes and subnets themselves do not run compute. | Keep the existing two-AZ/six-subnet design. Avoid adding endpoints, load balancers, or gateways without an approved requirement and cost review. |
| Security groups and rules (six SGs, sixteen standalone rules) | No separate hourly SG charge; traffic processed by other products remains billable. **Verify before apply.** | No direct recurring charge. | Preserve SG-to-SG scoping; do not use a public workload path as a cost shortcut. |
| ECS task IAM roles and execution policy (five resources) | No direct IAM role/policy charge under normal use; CloudTrail or dependent AWS API use may incur separate charges. **Verify before apply.** | No direct recurring charge. | Keep roles least-privilege; no additional products are required by this plan. |
| ECR repository and lifecycle policy | Repository configuration itself has no fixed hourly cost; stored image bytes, transfer, and any selected scan features can incur charges. **Verify before apply.** | Storage/transfer dependent. Cost grows as images are pushed and retained. | Keep immutable tags and the current lifecycle limit; remove obsolete images only under the reviewed retention/rollback policy. No image is pushed by this Terraform plan. |
| Cloud Map private DNS namespace and service definition | **Yes, potentially recurring.** Private namespace/registered-instance and DNS query pricing may apply; verify current pricing. | Namespace can incur charges while it exists; query/instance charges depend on actual use. This plan creates no ECS service or registered task instances. | Keep the one private namespace/service required for private discovery. Avoid extra namespaces/services and unnecessary DNS query volume. |
| CloudWatch/logging | No log group or alarm is created by this plan. IAM merely grants future log-stream/event actions under a prefix; that permission is not a CloudWatch resource charge. Future log ingestion/storage/metrics are usage-dependent. **Verify before apply/deployment.** | No baseline log ingestion from resources in this plan. | Create only required log groups in a later approved phase, set finite retention, and avoid high-cardinality/custom metrics unless required. |
| S3 remote-state backend | **Not included in this plan.** If enabled later, S3 storage, requests, versioned-object retention, and possible KMS charges apply. **Verify before backend initialization.** | Usage-dependent external dependency; bucket must be bootstrapped separately. | Keep state small, protect required versions, avoid unnecessary requests, and configure lifecycle only after state recovery policy approval. Do not add DynamoDB locking. |
| ECS/Fargate | **Not included in this plan.** Future tasks are billed by provisioned vCPU/memory and runtime; image pulls, logs, and network egress may add costs. **Verify before deployment.** | No ECS compute baseline from this Terraform stack. | Use private app subnets and no public task IP. Schedule the lab and scale only within approved test needs; retain private networking. |
| RDS PostgreSQL | **Not included in this plan.** Future DB instance hours, storage, I/O, backups, and data transfer may be billable. **Verify before deployment.** | No RDS baseline from this Terraform stack. | Use the separately approved smallest suitable disposable configuration and retention; keep the data tier private and avoid deleting retained data without approval. |
| ElastiCache Redis/Valkey | **Not included in this plan.** Future node hours, storage, and transfer may be billable. **Verify before deployment.** | No cache baseline from this Terraform stack. | Use the separately approved minimal node/topology; keep it private and schedule lab use where operationally supported. |

## Baseline assessment

The exact planned recurring baseline resources are:

1. **One NAT Gateway**, the primary meaningful fixed network cost, plus its data processing.
2. **One NAT Elastic IP/public IPv4 address**, subject to current AWS public IPv4 pricing.
3. **One Cloud Map private DNS namespace**, subject to current namespace/instance/query pricing.
4. **ECR storage and data transfer only after images are pushed**, and the external S3 state bucket only after it is separately provisioned and enabled.

VPC, six subnets, route tables, IGW, security groups, IAM roles, and their rules do not create the principal direct hourly baseline in this plan. Terraform itself does not create Fargate, RDS, Redis/ElastiCache, or CloudWatch log groups.

The current architecture retains **one NAT Gateway**. It is intentionally not multi-AZ egress HA. Do not add another NAT Gateway as part of this review. Confirm current `eu-north-1` pricing for NAT hours/data processing, public IPv4, Cloud Map, ECR, and any backend bucket before approval.

## Approval

- Cost approval required: **YES**
- Cost approval status: **NOT CONFIRMED**
- Current prices: **verify before apply**
- One-NAT design retained: **YES**
