# AWS Test Laboratory Network Design

## 1. Executive summary

This document specifies a portable, isolated AWS environment for DCC and the standalone Test Laboratory in one dedicated VPC. It is a design only: it does not create infrastructure, configure AWS, or authorize a deployment.

**Recommendation:** create a dedicated VPC in `eu-north-1` for DCC and the Test Lab, rather than placing either service into the existing default VPC. Start with two Availability Zones and six subnets: one public, one private application, and one private data subnet in each AZ. Place DCC and Test Lab Fargate tasks in private application subnets; place RDS and Redis/Valkey in private data subnets. Use an Internet Gateway only for the public-subnet egress path; do not assign public IPs to application or data tasks.

For the first lab deployment, use one NAT Gateway in a public subnet to limit fixed network cost, with private-subnet default routes to it. This is intentionally not AZ-resilient egress; use one NAT Gateway per AZ if the lab’s availability requirements later justify the additional cost. An internal Cloud Map namespace is the recommended stable Test API endpoint. DCC diagnostics should resolve a running task’s current ENI private IP immediately before targeting that specific task.

Use Terraform for repeatable deployment and teardown. Begin with single-AZ RDS and a single-node Redis-compatible cache to control recurring cost, while spanning data subnet groups across two AZs so Multi-AZ/replication can be enabled later.

## 2. Task 33 findings and provenance

The design incorporates the following observed `eu-north-1` facts from the preceding read-only preflight:

- One visible VPC: `vpc-0a06f968e95a6421a`, `172.31.0.0/16`, available, default VPC.
- VPC DNS support and DNS hostnames are enabled.
- Three available subnets, each with 4091 free IPv4 addresses, in `eu-north-1a`, `eu-north-1b`, and `eu-north-1c`. All map public IPs on launch.
- The only route table is the main route table. It contains the local VPC route and an active `0.0.0.0/0` route to `igw-07fb776073f7531de`. All three subnets inherit this route.
- An Internet Gateway is attached. No NAT Gateway or private subnet tier was found.
- The only security group in the VPC is its default group. It permits all protocols from itself inbound and all egress.
- ECS/Fargate APIs are available; Fargate capacity providers are active. No ECS clusters, task definitions, services, or tasks were found.
- ECR, RDS, ElastiCache, CloudWatch Logs, and CloudWatch APIs were accessible. No ECR repositories, RDS instances/subnet groups, ElastiCache resources/subnet groups, CloudWatch log groups, ECS CloudWatch metrics, or alarms were found.
- PostgreSQL and Redis/Valkey engine APIs returned supported options. Sampled PostgreSQL orderable options indicated Multi-AZ capability across the three AZs.

**Provenance caveat:** the requested source file `docs/aws-test-lab-network-preflight.md` was not present in the workspace when this design was prepared. The facts above are transcribed from the read-only Task 33 results already observed in this conversation, not from that missing document. Before implementation, create or restore the Task 33 report at the requested path and reconcile it with this section. Do not treat this document as evidence of new AWS inspection.

The existing default VPC is recorded as observed state only. This design does not reuse, alter, or claim ownership of it.

### Documentation reconciliation

- The Task 33 findings above are supported by the previously recorded read-only CLI inspection in this conversation. A repository copy of `docs/aws-test-lab-network-preflight.md` was not available for independent verification.
- The observed findings and this document agree on a dedicated VPC, two initial AZs, private app/data placement, one NAT Gateway initially, Cloud Map for stable API discovery, and no public database/cache/task ENIs.
- The older `docs/deployment/aws-test-lab.md` proposal used VPC CIDR `10.42.0.0/16`, three API tasks, two worker tasks, and Prometheus/Loki/S3. Task 37 records the explicit resolution in [ADR-001](adr/ADR-001-test-lab-pre-apply-network-and-state.md): `10.80.0.0/16` and its six-subnet layout below are authoritative. The old CIDR is historical and superseded; service counts and optional telemetry remain separate scope decisions.
- The DCC ECS deployment guide describes the generic production deployment contract. Task 38 specifies that the DCC service for this architecture uses the same dedicated VPC and private application subnets as the Test API and Test Worker.
- Task 38's read-only regional inspection found no overlapping visible VPC CIDR and no peering, Transit Gateway attachment, or VPN connectivity resources. DCC-to-Test-Lab access requires no cross-VPC mechanism. Resolve remaining cost, permissions, state-backend, and service-deployment prerequisites before apply.

## 3. Existing VPC versus dedicated VPC

| Consideration | Reuse default VPC | Dedicated Test Lab VPC |
|---|---|---|
| Isolation | Shares current/default network and broad default SG behavior; weaker boundaries | Separate routes, subnets, SGs, DNS scope, and resource lifecycle |
| Simplicity | Fewer initial network components, but public subnet defaults are easy to misuse | Requires a small network baseline and explicit IaC |
| Cost | Lowest immediate network cost | VPC itself has no hourly charge; NAT/endpoints add cost |
| Portability | Depends on account-specific default VPC state and subnet layout | CIDR, subnet, and route design can be reproduced in another account/region |
| Cleanup | Risk of disturbing shared/default resources; ownership is ambiguous | Resources can be tagged and torn down as one environment |
| DCC integration | DCC would share the default network and broad default SG behavior | DCC and Test Lab share private application subnets and scoped SG references; no cross-VPC connection is needed |
| RDS/ElastiCache | Can technically use current subnets, but their shared/public routing is inappropriate | Dedicated multi-AZ private data subnet groups |
| Multi-AZ | Three AZs are visible, but all current subnets are public-routed | AZ count and subnet tiers are explicitly chosen |
| Operational risk | Accidental exposure and drift in shared defaults | More setup, but repeatable ownership and fewer implicit assumptions |

**Decision: Option B, dedicated Test Laboratory VPC.** The priorities are isolation, repeatability, portability, and meaningful DCC diagnostics, not just the lowest initial bill. A dedicated VPC also gives the standalone Test Lab a clear extraction boundary. DCC integration should be explicitly private and authorized; it should not depend on DCC code or its database.

The observed VPC can remain unchanged and serve other account workloads. Do not adopt its `172.31.0.0/16` CIDR for the new network without a separate overlap review.

## 4. Target architecture and Availability Zones

Use two AZs for the initial lab:

```text
AWS eu-north-1
└── dcc-testlab VPC
    ├── AZ-a
    │   ├── public subnet: NAT Gateway
    │   ├── private-app subnet: DCC, Test API, Test Worker, diagnostic workers
    │   └── private-data subnet: RDS/Redis subnet-group membership
    └── AZ-b
        ├── public subnet: reserved for a second NAT Gateway or future internal ingress
        ├── private-app subnet: DCC, ECS placement and task ENIs
        └── private-data subnet: RDS/Redis subnet-group membership
```

Two AZs are sufficient for the initial lab to spread ECS services, define a valid multi-AZ subnet group, and support future RDS Multi-AZ or replicated cache configuration. The normal target is at least two Test API tasks spread across the two AZs, plus one worker service. A disposable minimum-cost smoke-test run may temporarily use one API task, but that is not the resilient target. Three AZs are not required initially; each added tier/AZ increases address planning and can increase NAT or data-service cost. Add the observed third AZ later if higher placement capacity or AZ failure testing is required.

The initial topology has two public, two private-app, and two private-data subnets: **six total**. Only NAT or a deliberately selected ingress component belongs in public subnets. Place the DCC service, Test API, Test Worker, and diagnostic worker in private application subnets; do not place Fargate tasks or data services in public subnets.

## 5. CIDR plan

Authoritative Task 38 allocation, with two AZs and exactly six subnets:

```text
Test Lab VPC: 10.80.0.0/16

eu-north-1a
  public:       10.80.0.0/24
  private-app:  10.80.16.0/20
  private-data: 10.80.48.0/24

eu-north-1b
  public:       10.80.1.0/24
  private-app:  10.80.32.0/20
  private-data: 10.80.49.0/24
```

The `/20` application subnets provide thousands of addresses per AZ for Fargate task ENIs, deployment overlap, diagnostic workers, and later test workloads. `/24` public and data subnets provide hundreds of usable addresses each, adequate for the initial NAT/ingress and managed data subnet placements. RDS and cache ENIs consume few addresses relative to Fargate task churn.

This is the approved repository CIDR layout and has been checked against the AWS VPC/subnet inventory visible in `eu-north-1`: the only visible VPC is the default `172.31.0.0/16`, whose route table has only the local route and an IGW default route. No peering, Transit Gateway, or VPN resources/connections were returned. The proposed `10.80.0.0/16` does not overlap those visible CIDRs. DCC and Test Lab task communication is within the new shared VPC; no route to another VPC is part of this design. Any future external network connection requires a separate overlap review. Terraform now rejects subnet ranges outside the VPC and overlapping subnet ranges.

## 6. Public and private placement

| Subnet class | Resources |
|---|---|
| Public | NAT Gateway(s); optionally an internal-only load balancer is not public and belongs in private subnets. No public ALB is required for the first lab. |
| Private app | DCC ECS service, Test API ECS service, Test Worker ECS service, one-off diagnostic worker tasks, and optional private metrics/logging collectors. |
| Private data | RDS PostgreSQL and Redis/Valkey subnet-group membership |

All ECS task definitions should use `awsvpc`, private subnets, dedicated task SGs, and `assignPublicIp=DISABLED`. RDS and cache should have public access disabled.

DCC should also be private-only in this design. Human/operator access needs an approved private path (for example, an existing VPN, corporate network, or separately designed authenticated ingress). This document does not introduce a public DCC entry point or replace its existing deployment requirements.

## 7. Routing and egress

Create an IGW for the dedicated VPC and associate it with the VPC.

| Route table | Associated subnets | Routes |
|---|---|---|
| Public | Both public subnets | VPC CIDR → `local`; `0.0.0.0/0` → IGW |
| Private app | Both private-app subnets | VPC CIDR → `local`; `0.0.0.0/0` → NAT Gateway |
| Private data | Both private-data subnets | VPC CIDR → `local`; no default internet route |

Keep the data tier without direct internet egress. It needs only local VPC connectivity to approved clients. Add narrowly scoped endpoints only if a future data-management workflow requires AWS APIs.

### Egress strategy decision

| Option | Benefits | Costs/risks |
|---|---|---|
| NAT Gateway | Simple private task egress; supports ECR pulls, AWS APIs, external dependencies, and later external monitoring without public task IPs | Hourly and per-GB charges; broad network destination reachability unless constrained by SGs, endpoints, or egress controls; single NAT is an AZ dependency |
| VPC endpoints plus NAT | Private access to AWS services; can reduce NAT traffic and exposure | Interface endpoints have per-AZ/hour and data charges; more resources/policies to manage; not every external dependency has an endpoint |
| ECS in public subnets | Avoids NAT | Public task ENIs and larger exposure; not acceptable for this design |

**First implementation choice: Option A, one NAT Gateway** in `eu-north-1a`’s public subnet. Both private-app route tables point to that NAT. The second public subnet is reserved; do not add a second NAT until the higher-availability requirement is accepted. This is a cost-optimized lab decision with an explicit single-AZ egress failure mode and possible cross-AZ data transfer.

The default route through NAT supports ECR, CloudWatch Logs, Secrets Manager, ECS control-plane APIs, and other required HTTPS destinations. It does not make tasks publicly reachable. If egress must be constrained or NAT cost is material, evaluate these endpoints first: ECR API, ECR Docker registry, S3 gateway (ECR image layers), CloudWatch Logs, Secrets Manager, and Systems Manager only if ECS Exec/SSM is approved. Endpoint SGs and endpoint policies must be scoped. Interface endpoint charges must be compared with NAT charges; they are not automatically cheaper.

Security groups do not filter outbound HTTPS by DNS name. If policy requires domain-level egress allowlisting, NAT alone is insufficient; evaluate a managed egress firewall/proxy or endpoint-only access and explicitly account for every required AWS/external destination.

## 8. ECS networking

| Workload | Launch | Network mode | Placement | Public IP | SG |
|---|---|---|---|---|---|
| Test API service | Fargate | `awsvpc` | Private-app subnets in both AZs | Disabled | `test-api-sg` |
| Test Worker service | Fargate | `awsvpc` | Private-app subnets in both AZs | Disabled | `test-worker-sg` |
| Diagnostic worker | Fargate one-off task, started by DCC | `awsvpc` | Private-app subnets in both AZs | Disabled | `diagnostic-worker-sg` |

Each Fargate task receives its own task ENI and private address. Services should use placement across both AZs and capacity-provider strategy appropriate to cost and testing. The diagnostic worker must receive a task identity (ARN or cluster plus task ID), not a long-lived IP. Resolve the task with ECS `DescribeTasks`, verify it is `RUNNING`, extract its `awsvpc` ENI/private IPv4 address, and use that address for the diagnostic operation.

To handle task replacement, re-resolve just before a run and refresh after connection failures. Verify the task ARN and lifecycle state again before retrying; never assume an old IP still belongs to the original target. Keep the task ARN as the correlation identity in diagnostics and logs. Do not cache task IPs beyond a bounded operation.

The DCC backend’s role should be the authority for starting/stopping the diagnostic task and passing only its task role. Whether the diagnostic worker itself needs ECS `DescribeTasks` permission depends on where resolution is implemented. Prefer resolving in DCC and passing a short-lived target IP plus task ARN if this fits the current lifecycle; otherwise grant the worker only the required describe permissions. Avoid giving the Test Lab tasks DCC control-plane permissions.

## 9. Test API endpoint strategy

| Option | Use |
|---|---|
| Direct task private IP | Required for testing one specific running task; transient and must be freshly resolved |
| Internal ALB | Stable endpoint and health-based balancing; adds hourly/data costs and diagnoses the load-balanced service rather than one selected task |
| Cloud Map / ECS Service Connect | Stable private service name without a public endpoint; Cloud Map directly supports DNS discovery, while Service Connect adds managed proxy behavior |
| Combination | Use stable service DNS for ordinary service-level calls and the task ENI address for per-task diagnostics |

**Recommendation:** private Cloud Map service discovery for the stable Test API service endpoint, plus direct task-private-IP targeting for task-specific diagnostics. No ALB is needed for the initial lab. If operators later require centralized health checks, TLS termination, or a stable multi-service entry point, evaluate an internal ALB separately. DNS service discovery is not a substitute for task state validation: use ECS identity and fresh ENI resolution for a selected task.

The Test API listens on TCP 8080. It has no built-in authentication, so it must never be exposed publicly; its foundation SG permits only the diagnostic-worker and DCC control SGs. Both source SGs belong to ECS tasks in the same VPC/private application subnets.

## 10. Security groups

Create dedicated groups; do not attach the observed default SG to lab tasks or data services.

| SG | Inbound | Egress |
|---|---|---|
| `dcc-control-sg` | No inbound rule in this foundation | TCP 8080 to `test-api-sg`; HTTPS 443 for AWS API access through NAT |
| `diagnostic-worker-sg` | No unsolicited inbound application traffic | TCP 8080 to `test-api-sg`; approved dependency/telemetry paths only |
| `test-api-sg` | TCP 8080 from `dcc-control-sg` and `diagnostic-worker-sg`; metrics scrape source only if distinct | TCP 5432 to `rds-sg`; TCP 6379 to `redis-sg`; approved DNS and AWS egress |
| `test-worker-sg` | No inbound application listener; optionally metrics port 9101 from approved Prometheus scraper only | TCP 5432 to `rds-sg`; TCP 6379 to `redis-sg`; approved DNS and AWS egress |
| `rds-sg` | TCP 5432 from `test-api-sg` and `test-worker-sg` only | Stateful response traffic; do not add broad outbound access without an identified need |
| `redis-sg` | TCP 6379 from `test-api-sg` and `test-worker-sg` only | Stateful response traffic; do not add broad outbound access without an identified need |
| `alb-sg` (only if an internal ALB is later selected) | Listener port from explicitly approved DCC/monitoring SGs | TCP 8080 to `test-api-sg` |

Security groups are stateful. Use SG references for service-to-service flows rather than subnet CIDRs. A scrape agent should be given only the required metrics port; do not open 9101 to the VPC or internet generally. DNS access uses the VPC resolver and its AWS-managed behavior; do not add arbitrary inbound DNS rules to task SGs.

### Final flow matrix

| Source SG | Destination SG | Protocol/port | Purpose |
|---|---|---|---|
| `dcc-control-sg` | `test-api-sg` | TCP 8080 | Private DCC-to-Test-API request |
| `diagnostic-worker-sg` | `test-api-sg` | TCP 8080 | Diagnostic request to a selected API task |
| Internal ALB SG (optional) | `test-api-sg` | TCP 8080 | Stable internal API endpoint |
| `test-api-sg` | `rds-sg` | TCP 5432 | API database activity |
| `test-api-sg` | `redis-sg` | TCP 6379 | API cache activity |
| `test-worker-sg` | `rds-sg` | TCP 5432 | Worker database activity |
| `test-worker-sg` | `redis-sg` | TCP 6379 | Worker cache activity |
| Approved scraper SG | `test-api-sg` | TCP 8080 | API `/metrics`, if scraping API in place |
| Approved scraper SG | `test-worker-sg` | TCP 9101 | Worker metrics scraping |

The Terraform foundation creates the DCC control SG and a narrowly scoped SG-reference path to the Test API. The DCC service must attach this SG and use the same private application subnets. This SG has no inbound rules; DCC operator ingress is a separate deployment concern and must not be made public. No cross-VPC path, CIDR-wide ingress, or public task IP is required.

## 11. RDS PostgreSQL

- Engine: a currently supported PostgreSQL version, selected at implementation time from `eu-north-1` orderable options; do not pin to the old sample versions from preflight.
- Subnet group: both private-data subnets, in two distinct AZs.
- Public accessibility: disabled.
- Port: TCP 5432.
- Security group: `rds-sg`, inbound only from the API and worker SGs.
- Encryption: enable storage encryption with an approved KMS key; use TLS for client connections where supported/configured.
- Credentials: inject via Secrets Manager or an approved secret system. Do not put passwords in Terraform state outputs, image layers, source, or plain task-definition environment values.
- Backups: enable automated backups with a short lab-appropriate retention (for example, 1–7 days) and test restore only in an approved non-production workflow.
- Multi-AZ: subnet coverage must support it. For the initial cost-conscious lab, begin Single-AZ but retain two-AZ subnet-group membership. Enable Multi-AZ for availability/failover test phases and keep it enabled if the lab becomes operationally important.
- Deletion protection: keep disabled only for an explicitly disposable lab with a controlled teardown procedure; require an explicit IaC variable/approval and final snapshot before deletion. If data retention matters, enable deletion protection.
- Use a dedicated app database/user with least privilege. The Test Lab must not use the DCC database.

## 12. ElastiCache Redis/Valkey

- Use a currently supported Redis-compatible engine (Redis or Valkey) after verifying client compatibility and regional option support at implementation time.
- Place it in a cache subnet group spanning both private-data subnets; no public address.
- Port: TCP 6379, inbound only from `test-api-sg` and `test-worker-sg`.
- Enable at-rest and in-transit encryption; provide the service a TLS endpoint/URL (`rediss://`) and credentials through a managed secret.
- Enable AUTH/token or the supported user-group access control appropriate to the selected engine. Rotate through the approved secret process.
- Start with a single node/no replica for minimum recurring cost if cache loss is acceptable. Use replication/failover when testing availability behavior or when worker/API test state must survive a node failure.
- Do not share a production cache or flush any shared Redis database.

## 13. Observability and network paths

**CloudWatch is the baseline.** Configure ECS `awslogs` for API, worker, DCC, and diagnostic worker stdout/stderr. Create dedicated log groups with explicit retention through IaC. The ECS task execution role needs only the permissions required to create streams and put events in the specific groups. Container Insights may be enabled for ECS-level metrics after its cost and permissions are reviewed.

The Test API exposes Prometheus metrics on its API listener (8080 `/metrics`); the worker exposes metrics on its separate 9101 listener. Metrics are not pushed by the application. A future Prometheus scraper may run privately or be an approved external system connected through private networking. Grant scrape access only to its SG. Loki is optional and not deployed by this design; if selected later, document endpoint ownership, TLS/authentication, private connectivity, retention, and egress rules first.

DCC accesses operational logs/metrics through authorized AWS APIs or the approved Prometheus/Loki endpoint. Do not make task ports, CloudWatch endpoints, or dashboards public for convenience. During phase one, CloudWatch Logs and AWS-managed ECS metrics are the minimal baseline; app-level Prometheus scraping can be a later phase.

## 14. DCC diagnostic workflow and failure tests

```text
Operator on approved private access path
  -> DCC service
  -> DCC backend starts one diagnostic Fargate task
  -> diagnostic worker resolves target ECS task identity
  -> worker reads current ENI private IP and confirms RUNNING state
  -> worker sends bounded requests to target TCP 8080
  -> Test API performs controlled app work and optional DB/cache calls
  -> worker stops cleanly; logs/metrics correlate through task ARN and request ID
```

Network paths:

1. DCC backend to ECS control plane: HTTPS egress through NAT or approved ECS interface endpoint, authorized by its task role.
2. DCC backend to diagnostic task launch: ECS `RunTask`/`DescribeTasks`/`StopTask` and narrowly scoped `iam:PassRole`; not a security-group flow.
3. Diagnostic worker to selected Test API ENI: private VPC route, TCP 8080, worker SG to API SG.
4. Test API to PostgreSQL: VPC-local route, TCP 5432, API SG to RDS SG.
5. Test API to Redis/Valkey: VPC-local route, TCP 6379, API SG to cache SG.
6. Test Worker to PostgreSQL and Redis: same private data paths using worker SG.
7. ECS tasks to CloudWatch/ECR/Secrets Manager: task execution role plus NAT egress or selected VPC endpoints.

The design permits application-level CPU, memory, latency, mixed-workload, and HTTP-error diagnostics without broader network permissions. To test dependency failures or latency, use a dedicated disposable environment and explicit test controls (for example, service configuration or a controlled proxy); do not change shared production SGs or routes as a fault-injection shortcut. Fargate does not imply permission to use host-level network tools such as `tc`; network-latency experiments may require an approved proxy or separate fault-injection design.

## 15. Portability and configuration contract

The Test Lab remains independently deployable. It does not import DCC code, use the DCC database/authentication, or require DCC-specific runtime dependencies. DCC integration is a network/IAM concern, not a source dependency.

Make the following configurable in Terraform variables and/or CloudFormation parameters, then pass only application-specific settings through ECS task definitions:

| Configuration | Examples |
|---|---|
| Naming/environment | project prefix, environment, owner, purpose, immutable image tags |
| Region/network | region, VPC CIDR, AZ names, subnet CIDRs, NAT count, endpoint selection |
| ECS | cluster/service names, task CPU/memory, desired/max count, deployment strategy, health check, capacity providers |
| API/worker | `APP_NAME`, `APP_VERSION`, `ENVIRONMENT`, `SERVICE_NAME`, `PORT`, worker interval/metrics port, workload safety limits |
| Dependencies | `DATABASE_URL` and `REDIS_URL`, assembled from secret references rather than committed values |
| Security/observability | SG IDs/rules, log group/retention, metrics scraper SG, CloudWatch/Prometheus/Loki endpoints |
| Persistence | PostgreSQL engine/class/storage/backups/Multi-AZ/deletion behavior; cache engine/node/replication/encryption/auth |
| Ownership | KMS key, secret identifiers, role ARNs, approved DCC/diagnostic worker integration |

Keep hostnames, passwords, account-specific IDs, VPC/subnet IDs, and security-group IDs out of source code. The service’s independent environment contract is documented in `test-app/INTEGRATION.md`.

## 16. IAM model

Use separate roles and do not grant the Test Lab DCC administration permissions.

| Role | Intended permissions |
|---|---|
| DCC ECS task role | Only DCC API operations required for configured discovery/diagnostics; narrowly scoped task describe/list, run/stop on approved diagnostic task definitions/cluster, and `iam:PassRole` only for the diagnostic task/execution roles |
| DCC diagnostic worker task role | No ECS permissions if DCC resolves target identity and passes it safely; otherwise only the minimum describe operation needed to re-resolve approved target tasks |
| Test API task role | No AWS permissions by default |
| Test Worker task role | No AWS permissions by default |
| ECS task execution role | ECR image pull, CloudWatch log stream/event delivery, and retrieval of named Secrets Manager/SSM secret references as applicable |

Keep the execution role (agent actions to start the container) separate from the application task role (permissions used by code). ECS retrieves task-definition secret references with the execution role; do not grant the application role secret access unless application code itself must call Secrets Manager.

If DCC needs AWS-hosted inventory, metrics, or logs, add only the relevant read operations to the DCC role, such as ECS describe/list, CloudWatch `GetMetricData`/`GetMetricStatistics`, and CloudWatch Logs read/filter actions. Scope log resources and supported ECS resources to this environment. Scope `RunTask` to approved diagnostic task definitions and the intended cluster; scope `iam:PassRole` only to the diagnostic task/execution roles with the ECS task-service condition. Verify AWS resource-level support for each action during implementation; document any unavoidable wildcard resource and constrain it with conditions where supported. No IAM resources or policies are created by this specification.

## 17. Naming and tags

Use stable names independent of task IDs:

```text
dcc-testlab-vpc
dcc-testlab-public-a / dcc-testlab-public-b
dcc-testlab-private-app-a / dcc-testlab-private-app-b
dcc-testlab-private-data-a / dcc-testlab-private-data-b
dcc-testlab-rt-public / dcc-testlab-rt-private-app / dcc-testlab-rt-private-data
dcc-testlab-sg-diagnostic-worker / dcc-testlab-sg-test-api
dcc-testlab-sg-test-worker / dcc-testlab-sg-rds / dcc-testlab-sg-redis
dcc-testlab-cluster
dcc-testlab-api / dcc-testlab-worker
dcc-testlab-app-repo                                # one shared API/worker image repository
dcc-testlab-postgres
dcc-testlab-redis
/ecs/dcc-testlab/api
/ecs/dcc-testlab/worker
/ecs/dcc-testlab/diagnostic-worker
dcc-testlab-dcc-task-role / dcc-testlab-diagnostic-task-role
dcc-testlab-api-task-role / dcc-testlab-worker-task-role
dcc-testlab-execution-role
```

Do not encode temporary task IDs in resource names.

Apply required tags where supported:

```text
Project=DCC-TestLab
Environment=lab
ManagedBy=IaC
Owner=<configurable>
Purpose=<resource-purpose>
```

Enable cost allocation tags for the project/environment/owner dimensions after reviewing account billing practice. Never put credentials or sensitive diagnostic data in tags.

## 18. Infrastructure as Code

**Recommendation: Terraform.** It supports reusable modules, plan review, explicit dependency graphs, remote state, and complete environment teardown. Use a pinned Terraform/provider version, remote encrypted state with locking, and reviewed plans. State may contain sensitive identifiers or secret metadata; do not store secret values as Terraform outputs or plaintext variables.

Proposed module/component structure:

```text
network
  ├── VPC, subnets, IGW, NAT, route tables, optional endpoints
security
  └── dedicated task/data/endpoint SGs and narrow SG references
ecr
  └── API and worker repositories, immutable image tag policy
iam
  └── execution roles, DCC role, diagnostic role, API/worker task roles
secrets
  └── secret containers/ARN wiring; secret values supplied securely out of band
rds
  └── PostgreSQL subnet group, parameter settings, instance and backups
redis
  └── Redis/Valkey subnet group and cache
observability
  └── log groups/retention, optional Container Insights/scrape connectivity
ecs
  └── cluster, task definitions, API/worker services and diagnostic task definition
```

Dependency ordering:

```text
network -> security -> iam/ecr
network + security + secrets -> rds/redis
network + security + iam + ecr + secrets + observability -> ecs API/worker
ecs cluster/task definition + iam + security -> DCC integration/diagnostic task
```

Avoid a module cycle between security groups and ECS services: define SGs and rules using SG IDs and planned service roles before creating ECS services. The approved DCC/Test Lab deployment uses the same VPC; a separate-VPC placement is outside this architecture and is not part of this task.

## 19. Cost considerations

Relative cost is indicative only. Actual prices vary by region, usage, retention, transfer, engine, capacity, and purchase options; consult current AWS pricing before approval.

| Component | Relative impact | Cost notes |
|---|---|---|
| NAT Gateway | High fixed + data | One gateway is the initial lab choice; two gateways improve AZ resilience but roughly duplicate fixed gateway cost |
| Internal ALB | Medium | Omitted initially; hourly and LCU charges |
| ECS Fargate | Low–medium | Depends on task count, CPU/memory, architecture, and runtime |
| RDS | Medium–high | Single-AZ small instance keeps cost down; Multi-AZ and storage/backups increase it |
| ElastiCache | Medium | Single node is the least-cost realistic baseline; replicas and larger nodes cost more |
| CloudWatch | Low–medium | Log ingestion, storage, custom metrics, Container Insights, and alarms are usage-priced |
| ECR | Low | Storage, scan features, and data transfer vary |
| Prometheus | Medium–high | Managed workspace or always-on scraper has ongoing cost |
| Loki | Medium–high | Compute/storage/retention and data transfer; no deployment in initial baseline |

Minimum-cost initial deployment that still yields useful diagnostics: two-AZ private app/data subnet coverage, one NAT Gateway, one API task with a small controlled scale ceiling, one worker, Single-AZ PostgreSQL, one Redis-compatible node, CloudWatch logs with short retention, and no ALB or always-on Prometheus/Loki. This sacrifices egress-AZ resilience and database/cache failover; explicitly accept that before implementation.

## 20. Cleanup strategy

Use Terraform ownership and tags so all lab resources are discoverable. Teardown order should reverse dependencies:

1. Stop diagnostic runs and reduce/stop DCC/Test API/worker services.
2. Remove ECS services and task definitions after confirming no running tasks depend on them.
3. Preserve or delete RDS/cache data according to an explicit retention decision; take final RDS snapshot if required.
4. Delete Redis/Valkey only after deciding whether cache data is disposable.
5. Remove log groups only after required diagnostic evidence is exported; retain or expire according to approved retention.
6. Delete secrets only after consumers and audit needs are resolved.
7. Delete ECR images/repositories according to retention policy.
8. Remove endpoint resources, NAT Gateway(s), and associated EIPs before route tables/subnets/VPC; confirm no shared dependencies.
9. Remove security groups/roles after all referencing tasks/services/policies are detached.
10. Destroy the dedicated VPC only after state and resource inventory show no remaining dependencies.

NAT Gateways and EIPs can outlive services if not explicitly removed. RDS final snapshots, backups, and retained log groups can also persist and incur cost. IaC destroy must not silently delete persistent data: require explicit variables/approval for final snapshot and retention behavior. Never tear down the observed default VPC as part of Test Lab cleanup.

## 21. Implementation phases

These are future phases only; none is executed by this document.

1. **Network:** approve CIDR non-overlap; create dedicated VPC, two-AZ public/app/data subnets, route tables, IGW, and selected NAT design.
2. **Security and IAM:** create dedicated SGs, secret access boundaries, DCC/worker/task roles, and reviewed PassRole scope.
3. **ECR:** create API/worker repositories, lifecycle/immutability policy, and publish approved images through a separate authorized task.
4. **RDS and Redis:** create private subnet groups and single-node lab data services with encryption, credentials, backup, and deletion controls.
5. **Test API and Worker ECS:** create private Fargate services, health checks, CloudWatch logs, secrets injection, metrics access policy, and Cloud Map DNS.
6. **DCC ECS service:** place DCC privately and grant only required discovery/diagnostic-task permissions; preserve existing architecture.
7. **Diagnostic worker networking:** launch a diagnostic task in private app subnets, resolve current target ENI, and verify SG-to-SG TCP 8080 reachability.
8. **Observability:** validate CloudWatch logs/metrics, then add approved Prometheus/Loki connectivity only if needed.
9. **End-to-end diagnostic validation:** exercise safe bounded workload, request-ID/task-ARN correlation, failure/stop cleanup, and task replacement/IP refresh.

Each phase requires its own change review and explicit authorization. This design task executes no phase.

## 22. Risks and open questions

- The original Task 33 source document is missing; Task 38 repeated the relevant read-only regional network inspection for this gate.
- The AWS inspection sees only the default VPC `172.31.0.0/16` in `eu-north-1`; the DCC runtime VPC does not yet exist and **will be created by the approved Test Lab/DCC deployment architecture**. The proposed `10.80.0.0/16` does not overlap the visible regional VPC/subnet CIDRs.
- The current preflight confirms the observed default VPC is accessible but does not establish permissions to create dedicated infrastructure.
- Two AZs support the intended placement pattern, but a single NAT introduces an AZ failure and cross-AZ egress dependency.
- DCC and Test Lab task communication uses same-VPC private networking and SG references. No peering, Transit Gateway, VPN, PrivateLink, or public connectivity between them is required or selected.
- Private access for human operators and CI/CD has not been selected.
- Direct task-IP diagnostics depend on fresh ECS task-state/ENI resolution and careful stale-target handling; Cloud Map is only the stable service path.
- Diagnostic requests are powerful workload controls. Network restrictions, DCC safety limits, API input bounds, and IAM task-start limits must all remain enforced.
- Fargate does not guarantee arbitrary OS-level network fault injection. A separate proxy-based test design may be required for network latency/loss experiments.
- The choice of PostgreSQL version/class, Redis versus Valkey, cache auth model, backup retention, deletion protection, and final snapshot policy needs cost and compatibility approval.
- CloudWatch APIs are accessible but no lab log groups or metrics exist. Log retention, Container Insights charges, Prometheus placement, and Loki ownership remain undecided.
- NAT, data services, and observability have ongoing charges. Set budget alerts through the account’s approved process before deployment.

## 23. Validation and change boundary

Task 38 updated the Terraform security-group foundation and architecture documentation, then ran formatting, validation, CIDR-negative-case checks, and a read-only Terraform plan. AWS inventory was read-only. No AWS configuration or infrastructure was changed; no `terraform apply`, import, destroy, CloudFormation/CDK operation, image push, or deployment was performed.
