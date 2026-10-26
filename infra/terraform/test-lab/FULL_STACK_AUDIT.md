# DCC + Test Lab Full-Stack Audit

**Audit time:** 2026-10-26 08:02 +03:00  
**AWS account:** `366314473733`  
**Region:** `eu-north-1`  
**VPC:** `vpc-0b196d7bdefb910fc` (`10.80.0.0/16`)  
**ECS cluster:** `dcc-testlab-cluster`

## Executive result

**Overall status: PASS — the existing DCC + Test Lab stack is deployed and operational for the verified application paths.** All three ECS services are stable at 1/1/0, the running tasks use the expected immutable image digests in private subnets without public IPs, RDS and Redis are available/private/encrypted, both Cloud Map services have current task registrations, all requested private HTTP checks returned 200, and the Redis write/readback and PostgreSQL-backed API requests succeeded. The final Terraform plan reports **No changes**.

Cloud Map reports health metadata as `UNKNOWN`; both current registrations also carry `AWS_INIT_HEALTH_STATUS=UNHEALTHY`. This is not an ECS task-health result. Current DCC container health is `HEALTHY`, both DNS registrations resolve to the current private tasks, and private application requests succeeded. The Test Worker task has ECS health `UNKNOWN` because its task definition does not configure a container health check; its current logs are clean and the API readiness and dependency checks passed.

## Terraform state and configuration

- `terraform fmt -check -recursive`: **PASS**
- `terraform validate -no-color`: **PASS**
- `terraform state list`: **81 resources**
- `terraform plan -input=false -no-color`: **No changes. Your infrastructure matches the configuration.**
- No Terraform apply was performed during this audit update. The complete redeployment and reviewed applies are recorded in [APPLY_REPORT.md](./APPLY_REPORT.md).
- The existing local Terraform state was preserved. The DCC signing secret value was never printed or included in this report.

## AWS infrastructure inventory

### Network

- VPC `vpc-0b196d7bdefb910fc`, CIDR `10.80.0.0/16`; DNS support and hostnames enabled.
- Internet Gateway `igw-0e9bce38190897d04`, attached.
- NAT Gateway `nat-092a9535c92170234`, available in public subnet `subnet-0a7196b610f41e79c`.
- Public subnets:
  - AZ `eu-north-1a`: `subnet-0a7196b610f41e79c`, `10.80.0.0/24`
  - AZ `eu-north-1b`: `subnet-0fe488e8b077fb4a4`, `10.80.1.0/24`
- Private application subnets:
  - AZ `eu-north-1a`: `subnet-0107c10a8e8ab289f`, `10.80.16.0/20`
  - AZ `eu-north-1b`: `subnet-028c1d15210c04e4a`, `10.80.32.0/20`
- Private data subnets:
  - AZ `eu-north-1a`: `subnet-0041016aa8b7dd4a8`, `10.80.48.0/24`
  - AZ `eu-north-1b`: `subnet-041c530a4fed52aa9`, `10.80.49.0/24`
- Public subnets route to the IGW; private application subnets use the NAT route; private data subnets have only the VPC-local route.

### Security groups and connectivity

| Purpose | Security group | Verified scope |
|---|---|---|
| DCC control | `sg-06bf45d27e5bfb57f` | Private DCC ingress from diagnostic worker; scoped egress to Test API and HTTPS |
| Diagnostic worker | `sg-0ec1a4bd3481b0a60` | Private egress to DCC TCP 8000, Test API TCP 8080, and HTTPS |
| Test API | `sg-05751820d0467cae4` | Ingress from DCC/diagnostic groups; egress to RDS TCP 5432 and Redis TCP 6379 |
| Test Worker | `sg-0033508ad3b0918dc` | Egress to RDS TCP 5432 and Redis TCP 6379; no app ingress |
| RDS | `sg-0d2fd9800eb0675fa` | TCP 5432 ingress only from Test API and Worker groups |
| Redis | `sg-05d450a6aa8aa7fe6` | TCP 6379 ingress only from Test API and Worker groups |

No public-CIDR ingress to workload/data groups or public ECS task IPs were found.

### Data services

- PostgreSQL RDS `dcc-testlab-postgres`: **available**, encrypted, private, `PubliclyAccessible=false`, private data subnet group.
- Redis replication group `dcc-testlab-redis`: **available**, private, encryption at rest and in transit enabled.
- Test API `/ready` reported PostgreSQL and Redis as `available`. `/api/products` and `/api/orders` both returned HTTP 200, and a Redis write/readback check succeeded.
- No database/cache credentials or secret values are included here.

### ECR images

| Repository | Immutable deployed tag | Exact deployed digest |
|---|---|---|
| `dcc-app` | `dcc-20261026-032757` | `sha256:549712cea4abc52cb8990a7d209febb9236d40df8eba1c167101aad23c0e83d7` |
| `dcc-testlab-app` | `test-20261026-031204` | `sha256:8a620d72cd2824f75ed87bea3f9b3dff960dbbbe41a0ba2a50bb30f014294d40` |

Both deployed image digests match the running task definitions and task image digests. The images were built for `linux/amd64`; the container user is `10001:10001` (explicit in the DCC task definition and image configuration). The script's environment/state/private-key/AWS-access-key image scan also passed against both local deployed image tags.

### Cloud Map

- Private DNS namespace: `dcc-test.internal`, ID `ns-pldp5s4z3wslalky`.
- DCC service: `dcc-app`, service ID `srv-bdp5hiigl5lgulvg`, DNS record type `A`; the current running DCC task is registered.
- Test API service: `dcc-test-api`, service ID `srv-kvulztfgrhedfvmw`, DNS record type `A`; the current running API task is registered.
- Private DNS was used successfully by the private smoke task for both service names.
- Cloud Map health metadata is `UNKNOWN` and `AWS_INIT_HEALTH_STATUS` is `UNHEALTHY` on both registrations; do not represent this metadata as `HEALTHY`. ECS container health and real private reachability were verified independently.

## ECS services and running tasks

Cluster: `dcc-testlab-cluster`. Every task uses a private application subnet, the service-specific security group, and `assignPublicIp=DISABLED`; inspected ENIs had no public IP association.

| ECS service | Desired/running/pending | Current task ID | Task definition | Image digest | Health/user | Subnet / security group |
|---|---:|---|---|---|---|---|
| `dcc-app-service` | `1/1/0` | `a87a679a82724237afc35ff628a81bd8` | `dcc-app:3` | `sha256:549712cea4abc52cb8990a7d209febb9236d40df8eba1c167101aad23c0e83d7` | `RUNNING/HEALTHY`, `10001:10001` | `subnet-028c1d15210c04e4a`, `sg-06bf45d27e5bfb57f` |
| `api-service` | `1/1/0` | `2ef8c846c6204edcb91c8ecb1b44467c` | `dcc-testlab-api:2` | `sha256:8a620d72cd2824f75ed87bea3f9b3dff960dbbbe41a0ba2a50bb30f014294d40` | `RUNNING/HEALTHY`; image user `10001:10001` | `subnet-028c1d15210c04e4a`, `sg-05751820d0467cae4` |
| `worker-service` | `1/1/0` | `80f2a55c70e94069a11ef437e1753746` | `dcc-testlab-worker:2` | `sha256:8a620d72cd2824f75ed87bea3f9b3dff960dbbbe41a0ba2a50bb30f014294d40` | `RUNNING`; ECS health `UNKNOWN` (no task health check); image user `10001:10001` | `subnet-0107c10a8e8ab289f`, `sg-0033508ad3b0918dc` |

All service deployments reported completed. DCC is registered in Cloud Map and its container health check is healthy.

## IAM, secrets, and logs

- ECS execution role: `dcc-testlab-execution-role`; supports ECR pulls, CloudWatch logging, and required secret retrieval.
- DCC task role: `dcc-testlab-diagnostic-task-role`; scoped ECS read permissions support configured DCC live service discovery.
- Test API and Worker task roles remain distinct and are used for their database/cache workload.
- DCC Django signing secret exists in Secrets Manager and is referenced by the ECS task definition through `secrets`; its value was not retrieved for this report.
- Log groups `/ecs/dcc-testlab/dcc-app`, `/ecs/dcc-testlab/api`, and `/ecs/dcc-testlab/worker` have current task streams. The latest current task streams were checked for traceback, permission/access-denied, Gunicorn startup, database, Redis, and secret/configuration errors; none matched.
- The worker's current stream contains successful periodic workload cycles. Historical failures from old/stopped tasks are not current service failures.

## Private application connectivity

A temporary one-off diagnostic task ran in the existing private application subnets and was stopped after its checks. It was not a persistent service.

| Application/check | Result |
|---|---|
| DCC `GET /api/health/` | **200** |
| DCC `GET /` | **200** |
| DCC discovered static JS asset | **200** |
| DCC `GET /api/services/` | **200**, 3 ECS services discovered |
| Test API `GET /health` | **200** |
| Test API `GET /ready` | **200**, PostgreSQL and Redis available |
| Test API `GET /metrics` | **200** |
| Test API `GET /api/products` | **200** |
| Test API `GET /api/orders` | **200** |
| Redis write/readback | **PASS** |

These requests used private Cloud Map DNS names; the services were not made public.

## End-to-end dependency result

- **DCC → private VPC → ECS discovery:** PASS; `/api/services/` returned 200 and the DCC task role has the required scoped ECS read access.
- **DCC and Test API → private DNS:** PASS; both current Cloud Map task instances are registered and resolved by the in-VPC probe.
- **Test API → PostgreSQL:** PASS; readiness and PostgreSQL-backed products/orders requests returned successfully.
- **Test API → Redis:** PASS; readiness and Redis read/write/readback succeeded.
- **Test Worker → PostgreSQL/Redis:** PASS; current worker cycles report success; no current task error patterns were found.
- **Public exposure:** PASS; no public ECS task IPs, RDS is not publicly accessible, and Redis uses private subnets.

## Deployment readiness and reusable workflow

**Ready for the future one-command redeployment workflow.** The PowerShell entry point is [scripts/deploy-lab.ps1](../../../scripts/deploy-lab.ps1), documented in [ONE_COMMAND_DEPLOYMENT.md](../../../docs/deployment/ONE_COMMAND_DEPLOYMENT.md). The script's syntax and safety checks passed; it was not executed as part of this audit because executing it would rebuild and redeploy the stack.

The current Terraform root is monolithic, so the script reuses the existing state rather than staging foundation/data separately or using `terraform -target`. Its order is:

1. Verify prerequisites, account/region, and existing Terraform state.
2. Terraform init, format, and validation.
3. Backend tests, frontend typecheck/build, and Test Lab tests.
4. Build and push Test Lab image; retrieve exact ECR digest.
5. Build and push DCC image; retrieve exact ECR digest.
6. Create and inspect a fresh Terraform plan; reject unrelated/destructive actions and require explicit `APPLY` confirmation.
7. Apply the exact saved plan; wait for all ECS services to stabilize.
8. Verify task images, private network, RDS/Redis, Cloud Map, logs, and private application paths.
9. Require final Terraform plan `No changes`.

## Final readiness statement

**PASS — the current DCC + Test Lab lab stack is deployed and operational for the verified paths.** Terraform reports no drift. The only caveats are Cloud Map's `UNKNOWN` health metadata and the Test Worker task's unconfigured ECS health check; neither contradicts the verified running tasks, private registrations, and successful application/dependency checks.
