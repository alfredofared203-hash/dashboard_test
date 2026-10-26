# Task 41 — First Controlled AWS Apply Report

**Date:** 2026-10-25  
**Region:** `eu-north-1`  
**Result:** Successfully applied and verified. No AWS credentials or secret values are recorded here.

## 1. Pre-Apply Validation

- `terraform fmt -check -recursive`: PASS.
- `terraform validate -no-color`: PASS.
- Final plan: `52 to add, 0 to change, 0 to destroy`.
- Inspected the full planned resource action list. All 52 actions were creates in the approved Test Lab foundation: VPC/network and routes, NAT/EIP, security groups/rules, IAM, ECR, and Cloud Map. No ECS services, RDS, ElastiCache, CloudWatch log groups, replacements, or unrelated resources were planned.

## 2. Apply Result

- Result: SUCCESS. Applied the exact inspected saved plan.
- Terraform result: `52 added, 0 changed, 0 destroyed`.
- Approximate duration: 149 seconds.
- No `-auto-approve` flag was used. The command environment could not accept an interactive terminal confirmation, so Terraform applied the exact inspected saved plan.

## 3. AWS Resources Created

- **VPC:** `vpc-0b196d7bdefb910fc`, CIDR `10.80.0.0/16`.
- **Subnets:** six available subnets across `eu-north-1a` and `eu-north-1b`: two public, two private application, and two private data. Public-IP-on-launch is disabled on all six.
- **Routing/NAT:** one Internet Gateway (`igw-0e9bce38190897d04`); public subnets route to it. One NAT Gateway (`nat-092a9535c92170234`) is available in the first public subnet with an associated EIP allocation (`eipalloc-0e35a2754097be01d`). Both application subnets use the NAT default route. Data subnets have only the VPC-local route.
- **Security groups:** six dedicated DCC, diagnostic worker, Test API, Test Worker, RDS, and Redis groups. Test API ingress is scoped to the DCC control and diagnostic-worker groups; RDS/Redis ingress is scoped to the relevant application groups. No public ingress was found.
- **IAM:** four ECS task roles (execution, Test API, Test Worker, diagnostic worker) with ECS task trust. The execution role has the planned ECR pull and CloudWatch Logs write policy; application task roles have no attached or inline permissions.
- **ECR:** private repository `dcc-testlab-app`, immutable tags, scan-on-push enabled, AES256 encryption, and the planned lifecycle policy.
- **Cloud Map:** private DNS namespace `dcc-test.internal` (`ns-pldp5s4z3wslalky`) and `dcc-test-api` service (`srv-kvulztfgrhedfvmw`). Route 53 confirmed the private hosted zone is associated with the new VPC.

## 4. Post-Apply Verification

Read-only AWS CLI checks confirmed the VPC CIDR/state and DNS support/hostnames, all six subnet tiers/AZs, IGW attachment, route-table associations and route targets, NAT availability/EIP association, six security groups and rule relationships, four IAM roles and execution policy, ECR repository, and private Cloud Map namespace/service/VPC association.

No ECS clusters, RDS instances, or ElastiCache clusters were created; these are intentionally outside this foundation task. CloudWatch log groups and alarms were also not part of the approved plan.

**State note:** Terraform used the local backend. Preserve this workspace and its ignored `terraform.tfstate` files for future Terraform operations; no remote state backend was initialized.

## 5. Terraform Outputs

- Region: `eu-north-1`
- AZs: `eu-north-1a`, `eu-north-1b`
- VPC CIDR: `10.80.0.0/16`
- VPC ID: `vpc-0b196d7bdefb910fc`
- Public subnet IDs: `subnet-0a7196b610f41e79c`, `subnet-0fe488e8b077fb4a4`
- Private application subnet IDs: `subnet-0107c10a8e8ab289f`, `subnet-028c1d15210c04e4a`
- Private data subnet IDs: `subnet-0041016aa8b7dd4a8`, `subnet-041c530a4fed52aa9`
- NAT Gateway ID: `nat-092a9535c92170234`
- Security group IDs:
  - DCC control: `sg-06bf45d27e5bfb57f`
  - Diagnostic worker: `sg-0ec1a4bd3481b0a60`
  - Test API: `sg-05751820d0467cae4`
  - Test Worker: `sg-0033508ad3b0918dc`
  - RDS: `sg-0d2fd9800eb0675fa`
  - Redis: `sg-05d450a6aa8aa7fe6`
- ECR repository: `366314473733.dkr.ecr.eu-north-1.amazonaws.com/dcc-testlab-app`
- Cloud Map namespace/service IDs: `ns-pldp5s4z3wslalky`, `srv-kvulztfgrhedfvmw`
- IAM role ARNs and full Terraform outputs remain available via `terraform output`.

## 6. Next Blocker

None for proceeding to the next Test Lab deployment step in this working copy. Keep the local Terraform state with the workspace. ECS services, RDS, Redis/Valkey, and application deployment are not yet provisioned and belong to later tasks.

## 7. Status

**READY FOR NEXT TEST LAB DEPLOYMENT STEP**

## Task 42 — Data Layer Deployment Attempt

**Date:** 2026-10-25  
**Region:** `eu-north-1`  
**Result:** BLOCKED before apply. No AWS resources were changed by Task 42.

- `terraform fmt -check -recursive`: PASS.
- `terraform validate -no-color`: PASS.
- `terraform plan -input=false -no-color`: `0 to add, 6 to change, 0 to destroy`.
- The six proposed in-place changes affect existing DCC/Test Lab security groups (`dcc_control`, `diagnostic_worker`, `rds`, `redis`, `test_api`, and `test_worker`). The plan would remove ingress/egress entries currently represented on the security-group resources, including the API/worker-to-data SG relationships. These are unrelated to adding the data layer and could conflict with the existing standalone security-group rule resources.
- No planned destroy or replacement was reported, but the unrelated SG modifications violate the task's no-unrelated-changes condition. **Terraform apply was not run.**
- The current Terraform configuration contains no RDS DB instance/subnet group, ElastiCache cluster/replication group/subnet group, nor data-service variables or outputs. No credentials were added or exposed. AWS-side RDS or ElastiCache creation was not attempted.
- CloudWatch log groups are not required by the existing Terraform design for data services; no log groups were planned or created.

**Next blocker:** First reconcile the six existing security-group drift/ownership changes so a fresh plan leaves the deployed foundation unchanged; then add/review the intended private RDS and ElastiCache Terraform resources and their non-secret configuration. Re-run plan and apply only when the plan contains the intended data-layer additions and no unrelated foundation changes.

**Exact next recommended task:** Resolve Task 42 Terraform plan drift and implement a private RDS/ElastiCache data-layer plan without changing existing foundation resources.

**Task 42 status: BLOCKED.** The Task 41 apply result above remains unchanged.

## Task 43 — Data Layer Configuration and Plan Reconciliation

**Date:** 2026-10-25  
**Region:** `eu-north-1`  
**Result:** Configuration complete; clean plan produced. **No apply was performed.**

- Task 42 was blocked because its plan proposed six in-place updates to deployed security groups and had no RDS/ElastiCache resource definitions.
- Root cause: each `aws_security_group` declared empty inline `ingress`/`egress` collections while the same rules were managed by standalone `aws_vpc_security_group_*_rule` resources. During refresh the provider represented those standalone rules in the parent security-group attributes, so the explicit empty collections planned to remove them.
- Reconciliation: removed only the empty inline `ingress`/`egress` arguments from the six SG resources. The standalone ingress/egress rule resources remain unchanged as the authoritative rule definitions; no `ignore_changes` was added. The refreshed plan now has no SG or other existing-foundation actions.
- Added `aws_db_subnet_group.test_lab` and `aws_db_instance.test_lab` for encrypted, private PostgreSQL in the existing two private data subnets, attached to the existing RDS SG. RDS uses AWS-managed master credentials (`manage_master_user_password = true`); no password is configured or output.
- Added `aws_elasticache_subnet_group.test_lab` and a single-node Redis replication group in the existing private data subnets, attached to the existing Redis SG, with at-rest and in-transit encryption enabled and multi-AZ/failover disabled.
- Added non-secret outputs for identifiers, private endpoints, ports, and subnet-group names. No CloudWatch log groups are required or planned by these data-service resources.
- `terraform fmt -check -recursive`: PASS. `terraform validate -no-color`: PASS.
- Final plan: **4 to add, 0 to change, 0 to destroy** — exactly the RDS instance/subnet group and Redis replication group/subnet group. No existing SG or unrelated foundation resource is modified; no destroy or replacement is planned.
- **Apply: NOT RUN.** No AWS resources were changed by Task 43. The plan output was inspected and not retained as a long-lived plan artifact.

**Final status:** Ready for a separately authorized data-layer deployment plan review.  
**Exact next recommended task:** Review the four-resource Task 43 plan for AWS engine/class availability and then perform the controlled RDS/ElastiCache apply; do not include ECS deployment in that step.

## Task 44 — Data Layer Apply and Verification

**Date:** 2026-10-25  
**Region:** `eu-north-1`  
**Result:** Applied successfully; RDS and Redis verified available. No secrets are recorded here.

- **Read-only availability checks:** RDS reported PostgreSQL `18.3` as the regional default. The exact `db.t4g.micro` + PostgreSQL `18.3` + `gp3` orderable option was returned, with minimum storage 20 GiB and storage encryption support. ElastiCache reported Redis `7.1` as the regional default; `cache.t4g.micro` Redis reserved-node offerings were returned. The configuration leaves engine versions to AWS defaults; no Terraform configuration changes were made for availability.
- **Terraform validation:** `terraform fmt -check -recursive`: PASS; `terraform validate -no-color`: PASS.
- **Final pre-apply plan:** **4 to add, 0 to change, 0 to destroy**, exactly the RDS DB subnet group/instance and ElastiCache subnet group/replication group. No replacement or foundation/security-group action was present.
- **Apply:** SUCCESS using the exact inspected saved plan; approximately 490 seconds. Terraform reported **4 added, 0 changed, 0 destroyed**.
- **RDS:** `dcc-testlab-postgres` is `available`, PostgreSQL `18.3`, class `db.t4g.micro`, encrypted 20 GiB gp3 storage, port 5432, and single-AZ in `eu-north-1a`. Endpoint: `dcc-testlab-postgres.cluugiciepn3.eu-north-1.rds.amazonaws.com`. It uses VPC `vpc-0b196d7bdefb910fc`, subnet group `dcc-testlab-postgres-subnets` with the two private data subnets, and SG `sg-0d2fd9800eb0675fa`. `PubliclyAccessible` is false.
- **Redis:** replication group `dcc-testlab-redis` is `available`; its member node reports Redis `7.1.0`, class `cache.t4g.micro`, port 6379. Primary endpoint: `master.dcc-testlab-redis.5m5yg9.eun1.cache.amazonaws.com`. It uses subnet group `dcc-testlab-redis-subnets` in the same VPC/private data subnets and SG `sg-05d450a6aa8aa7fe6`. At-rest encryption and transit encryption are enabled; transit encryption mode is required.
- **Security:** read-only SG inspection found RDS TCP 5432 ingress only from Test API/Worker SGs (`sg-05751820d0467cae4`, `sg-0033508ad3b0918dc`) and Redis TCP 6379 ingress only from those same SGs. No IPv4/IPv6 CIDR ingress, including `0.0.0.0/0`, is configured on either data SG. RDS public accessibility is false. Both services are in private data subnet groups.
- **Terraform state/fresh plan:** local state now includes all four data-layer resources; preserve `terraform.tfstate` with this working copy. A fresh `terraform plan -input=false -no-color` returned **“No changes. Your infrastructure matches the configuration.”** No ECS cluster was created.
- **Apply authorization scope:** only the four reviewed data-layer resources were applied. No ECS, DCC service, or application deployment was performed.

**Final status:** Data layer deployed and verified; ready for the next Test Lab deployment step.  
**Exact next recommended task:** Deploy the Test Lab ECS cluster, API, and worker into the existing private application subnets using the existing security groups, Cloud Map service, and newly verified private database/cache endpoints. Do not expose the data services publicly.

## Task 45 — ECS Application Layer Deployment

**Date:** 2026-10-25  
**Region:** `eu-north-1`  
**Result:** BLOCKED before Terraform changes or apply.

- Read-only ECR inspection confirmed repository `dcc-testlab-app` exists at `366314473733.dkr.ecr.eu-north-1.amazonaws.com/dcc-testlab-app`.
- `aws ecr describe-images` returned no image details: there is no available image tag or digest to deploy.
- Per Task 45 instructions, no ECS Terraform resources were added, no `terraform plan` or `terraform apply` was run for the ECS layer, and no image was built or pushed. No AWS resources were changed.
- ECS cluster/services, task definitions, task logs, Cloud Map registrations, and smoke tests were not created or performed.

**Blocker:** The Test Lab application image must be built and pushed to the existing ECR repository under an agreed tag before ECS deployment can continue.  
**Exact next recommended task:** Build and push the Test Lab container image to `dcc-testlab-app`, record the resulting immutable tag/digest, then resume Task 45 using that exact image reference.

**Task 45 status: BLOCKED — no deployable ECR image.**

## Task 46 — Build and Push Test Lab Image

**Date:** 2026-10-25  
**Region:** `eu-north-1`  
**Result:** SUCCESS — one immutable, deployable application image tag is present in the existing ECR repository. No ECS or Terraform infrastructure was deployed or modified.

- **Build context/Dockerfile:** `test-app\`, using its existing `Dockerfile`; no Docker architecture or application code changes were made. The Docker build context was approximately 2.66 KB and `.dockerignore` excludes `.env` files, virtual environments, tests, and Git metadata.
- **Local build:** PASS, `linux/amd64`, non-root user `10001:10001`. The same image supports the default API command and documented Worker command `python -m worker.main`. Local API `/health` returned HTTP 200; API and Worker modules imported; Worker command exited cleanly in disabled mode.
- **Tests:** `python -m pytest -q` — **22 passed**, one upstream AnyIO deprecation warning.
- **Image review:** scanned 22 application source/requirements files for common AWS key, private-key, and token patterns; no matches. No `.env`, Terraform source, state, or plan files were present in `/app`.
- **AWS identity/region:** AWS STS identity query succeeded for the configured account. `aws configure get region` was empty; all ECR operations explicitly used `eu-north-1`. Credentials were not displayed.
- **ECR repository:** `366314473733.dkr.ecr.eu-north-1.amazonaws.com/dcc-testlab-app`; tag mutability is `IMMUTABLE`.
- **Immutable tag:** `test-20261025-235129` (timestamp-based because this workspace has no Git metadata).
- **Image digest:** `sha256:e1fcf841446fa2a34a27c066846d66bdddc6934c7d5c2c9a350c3f00ed419162`.
- **ECR verification:** tag resolves to the same digest as the local image. ECR reports an image size of 60,218,181 bytes and push time `2026-10-25T23:55:09+03:00`. The OCI index contains the `linux/amd64` image manifest plus its BuildKit attestation; ECR lists those two untagged OCI artifacts alongside the single tagged index. Exactly one new immutable deployable tag was pushed.
- **Remote-image smoke check:** pulled the tagged ECR image; verified `linux/amd64`, non-root user, API `/health` HTTP 200, and Worker command startup/exit in disabled mode.
- **AWS changes:** only the new immutable ECR image tag and its associated OCI image/attestation manifests were pushed. No repository settings, Terraform resources, ECS services, or other AWS resources were modified.

**Final status:** Image is ready for ECS task-definition/service deployment.  
**Exact next recommended task:** Resume Task 45 using the immutable image reference above (prefer the pinned digest); deploy only the private ECS application layer and verify API/Worker health, Cloud Map, logs, and data connectivity. Do not proceed to diagnostics or chaos testing in the ECS deployment step.

## Task 45 — ECS Application Layer Deployment (resumed after Task 46)

**Date:** 2026-10-25  
**Region:** `eu-north-1`  
**Result:** SUCCESS — the Test Lab API and Worker are running on ECS/Fargate in the existing private VPC. Existing foundation, RDS, Redis, security groups, ECR repository, and Cloud Map namespace/service were preserved.

- **Image:** `366314473733.dkr.ecr.eu-north-1.amazonaws.com/dcc-testlab-app@sha256:e1fcf841446fa2a34a27c066846d66bdddc6934c7d5c2c9a350c3f00ed419162` (immutable tag `test-20261025-235129`).
- **Terraform validation:** `terraform fmt -check -recursive`: PASS; `terraform validate -no-color`: PASS.
- **Pre-apply plan:** 8 to add, 0 to change, 0 to destroy. The reviewed additions were one ECS cluster, two task definitions, two services, two CloudWatch log groups, and one narrowly scoped execution-role policy granting `secretsmanager:GetSecretValue` only for the RDS-managed master secret. No VPC, subnet, SG, RDS, Redis, ECR, or Cloud Map resource was modified or replaced.
- **Apply:** SUCCESS. The first API service creation attempt was rejected because the existing Cloud Map service uses an A record and does not accept `container_name`/`container_port`. The Terraform service registry was corrected to reference the existing service ARN only; the follow-up plan contained only the API service creation. Final deployment totals: 8 resources added, 0 changed, 0 destroyed.
- **ECS cluster:** `dcc-testlab-cluster` (ACTIVE).
- **API service/task definition:** `api-service`, `dcc-testlab-api:1`; desired 1, running 1. Container is RUNNING and HEALTHY with the `/health` container health check.
- **Worker service/task definition:** `worker-service`, `dcc-testlab-worker:1`; desired 1, running 1. Container is RUNNING. Worker has no container health check configured; its application cycle logs report success.
- **Pinned image:** both task definitions use the exact digest above. API listens on TCP 8080; Worker runs `python -m worker.main`.
- **Private placement:** API uses subnet `subnet-028c1d15210c04e4a` and SG `sg-05751820d0467cae4`; Worker uses subnet `subnet-0107c10a8e8ab289f` and SG `sg-0033508ad3b0918dc`. Both are existing private application subnets in VPC `vpc-0b196d7bdefb910fc`. Their ENIs have private IPv4 addresses and no public IP association. No ALB, listener, public IP, or public ECS networking was added.
- **Cloud Map:** API is registered with the existing `dcc-test-api` service in private namespace `dcc-test.internal`. The private A record resolved to the API task IP `10.80.35.252`; no duplicate namespace or service was created.
- **Logging:** API logs are in `/ecs/dcc-testlab/api`; Worker logs are in `/ecs/dcc-testlab/worker`. Both log streams were observed.
- **Data connectivity:** Worker logs show successful Redis heartbeat operations and successful `worker_cycle_completed` events. A successful cycle requires both the PostgreSQL probe and Redis heartbeat to succeed. PostgreSQL password is injected from the RDS-managed Secrets Manager JSON `password` field as `PGPASSWORD`; the secret value is not stored in Terraform configuration or this report. Redis uses `rediss://` for the existing transit-encrypted cache.
- **Private API smoke test:** A one-off Fargate test task in the existing private application subnet and diagnostic-worker SG reached `http://dcc-test-api.dcc-test.internal:8080/health` and returned HTTP 200 with `{"status":"ok","application":"standalone-test-laboratory"}`. The temporary task stopped with exit code 0; its ENI was removed automatically. No permanent diagnostic service or infrastructure was created.
- **Final Terraform plan:** `No changes. Your infrastructure matches the configuration.`

**Resources added:** ECS cluster, API and Worker task definitions/services, API and Worker CloudWatch log groups, and the scoped execution-role secret policy (8 total).  
**Resources changed:** 0. **Resources destroyed:** 0.  
**Final status:** SUCCESS — API and Worker deployment verified.  
**Exact next recommended task:** In a separately authorized task, perform any additional application-level Test Lab validation desired; do not include diagnostics or chaos testing in this deployment task.

## Task 47 — AWS Test Lab Application-Level Validation

**Validation time:** 2026-10-26, 00:16–00:38 EEST (UTC+03:00)  
**Region:** `eu-north-1`  
**Overall result:** PASS, with the Cloud Map health-status limitation noted below. Validation was performed using the existing `dcc-testlab-cluster`; no Terraform apply or infrastructure creation was performed.

### Baseline

- **ECS:** Cluster `dcc-testlab-cluster` was ACTIVE. `api-service` and `worker-service` were ACTIVE, stable, and each had exactly 1 desired/running task. They used `dcc-testlab-api:1` and `dcc-testlab-worker:1`.
- **Image:** Both task definitions referenced `366314473733.dkr.ecr.eu-north-1.amazonaws.com/dcc-testlab-app@sha256:e1fcf841446fa2a34a27c066846d66bdddc6934c7d5c2c9a350c3f00ed419162`.
- **API:** RUNNING and HEALTHY. Worker was RUNNING; its ECS health status is UNKNOWN because its task definition has no container health check, which is not a failure for this workload.
- **Private networking:** API and Worker ENIs were in the existing application subnets in VPC `vpc-0b196d7bdefb910fc`, attached to their respective existing SGs, with private addresses and no public IP.
- **Data services:** `dcc-testlab-postgres` and `dcc-testlab-redis` were available. RDS was not publicly accessible; Redis transit encryption was enabled and its SG allowed the application SGs only.
- **Cloud Map:** Existing `dcc-test-api` in `dcc-test.internal` had a private A-record registration. The record resolved to the API task's private address.

### Private application endpoint results

One temporary Fargate task ran the test script from an existing private application subnet using the existing diagnostic-worker SG. Requests used `dcc-test-api.dcc-test.internal:8080`; all 13 requests returned the expected status, and each response echoed its request ID.

| Method/path | Status | Expected response summary | Request ID |
|---|---:|---|---|
| `GET /health` | 200 | `status=ok`, application `standalone-test-laboratory` | `task47-1e8e92fff2ec4dfabbc3f20ef18bb539` |
| `GET /ready` | 200 | ready; PostgreSQL and Redis both available | `task47-a76a8865ff8f431cb6539f4fd16546ec` |
| `GET /api/products?limit=10` | 200 | Two seeded products returned: test-book and test-mug | `task47-f5f0c9eae8a0471ca7af0b7b7232850a` |
| `GET /api/orders?limit=10` | 200 | Two seeded orders returned with expected products/statuses | `task47-ec17c16b6d0a406cb3986eaa7b2e9b26` |
| `GET /api/redis` (before write) | 200 | Fixed lab value key returned null | `task47-d3f75008ef314c758776d0785da1ed83` |
| `POST /api/redis` | 200 | Stored test value; response reported `stored=true`, length 23 | `task47-79a6a7e32d364881a73b700e5769e824` |
| `GET /api/redis` (after write) | 200 | Returned the value written by this test | `task47-51eae722a6574556945f7fc8a4ae51ba` |
| `POST /api/work/cpu` | 200 | CPU workload completed for requested 1 ms | `task47-77baa55507e146e98f3a2a1754b2f4ff` |
| `POST /api/work/latency` | 200 | Latency workload completed for requested 1 ms | `task47-2c5da921dc7c4cf5908a26d801facbe9` |
| `POST /api/work/memory` | 200 | Memory workload allocated 1,048,576 bytes | `task47-53480d86664548c4b8021c80f4026696` |
| `POST /api/work/mixed` | 200 | CPU/latency executed; PostgreSQL read one row; Redis increment executed | `task47-60cb777eb2ef4ac18d007e9e739b7e97` |
| `GET /api/work/error` | 500 | **Expected** controlled response `{"detail":"Intentional test error."}` | `task47-f52c4eab095f4e6a92b40552f417cda1` |
| `GET /metrics` | 200 | Prometheus text returned with HTTP, DB, Redis and workload metric families | `task47-313c0f86eec04ada86dd6569af690126` |

All listed endpoint statuses and response shapes matched the application contract/tests. The intentional workload error is a PASS for its documented controlled 500 behavior, not an unexpected failure.

### PostgreSQL, Redis, Worker, and API observability

- **PostgreSQL — PASS:** `/ready` reported PostgreSQL available; products and orders endpoints returned seeded database rows; `/api/work/mixed` reported PostgreSQL `executed` and one row read.
- **Redis — PASS:** `/ready` reported Redis available; `/api/redis` stored and read back the test value; `/api/work/mixed` reported Redis `executed`. Redis used the configured TLS endpoint.
- **Worker — PASS:** The service remained 1/1 running. Recent CloudWatch logs contained 50 successful `worker_cycle_completed` events; the recent sample contained no `worker_dependency_unavailable`, `redis_operation_failed`, or `database_operation_failed` events. Successful worker cycles execute both the PostgreSQL `SELECT 1` probe and Redis heartbeat.
- **API logs — PASS:** All 13 validation requests had corresponding `http_request_completed` JSON log entries with matching request IDs. An obvious-secret-pattern scan of those entries found no matches.
- **API metrics — PASS:** `/metrics` returned `text/plain; version=1.0.0; charset=utf-8`. Prometheus samples included the tested route/status counters and workload metrics, including the expected single 5xx counter for the intentional error endpoint.

### Recovery and cleanup

- **Recovery — PASS:** Triggered `aws ecs update-service --force-new-deployment` for `api-service` only. ECS replaced the API task; the replacement task `94e7a157ddac4d678658872e7e690584` became RUNNING and HEALTHY. Cloud Map updated to private IP `10.80.25.122`. A subsequent private smoke task verified `/health` and `/ready` both returned 200, with both dependencies available; their request IDs were `c30cdbf6-3b34-4c9e-8395-b01d9fe800a9` and `38cebd67-0243-4228-9060-835c9fcca847`, respectively. API and Worker returned to exactly 1 desired/running task each.
- **Temporary tasks — PASS:** Validation tasks `e7f32a46e03c4536b851886ff7bba491` and `c50957507155453eb4b29e14cb772693` stopped with exit code 0. Their task ENIs were removed; final ECS inspection showed only the API and Worker service tasks RUNNING. No temporary service, SG, load balancer, or other infrastructure was left behind.
- **Test data note — WARN:** The Redis write used the app's fixed lab value key and its documented 24-hour TTL. The API intentionally exposes no delete operation; the value will expire automatically. The existing products/orders endpoint lazily initializes its documented deterministic test tables/rows on first read.

### Terraform and limitations

- `terraform -chdir=infra/terraform/test-lab fmt -check`: PASS.
- `terraform -chdir=infra/terraform/test-lab validate -no-color`: PASS.
- `terraform -chdir=infra/terraform/test-lab plan -input=false -no-color`: **No changes. Your infrastructure matches the configuration.**
- Terraform apply was not run; local Terraform state was preserved.
- **Cloud Map — WARN, usable:** The existing `DNS_HTTP` service uses an A record and returns no separate `AWS_INSTANCE_HEALTH_STATUS` value. Its registration and private DNS A record were verified, and private health/readiness requests succeeded before and after API replacement. No Cloud Map service or namespace was changed.
- No public endpoint, public IP, ALB, listener, or cross-VPC connectivity was introduced.

**Task 47 status: PASS.** Application-level API, PostgreSQL, Redis, Worker, metrics, logging, private routing, recovery, cleanup, and Terraform no-drift checks passed.  
**Exact next recommended task:** Continue with the next separately scoped Test Lab task; retain the existing Terraform state and do not expose the Test Lab API publicly.

## DCC ECR repository creation - Task 48A

**Validation date:** 2026-10-26  
**AWS region:** `eu-north-1`  
**Result:** **PASS**

- Inspected the existing Terraform configuration and local state. AWS confirmed `dcc-testlab-app` exists as the immutable Test Lab repository and `dcc-app` did not exist before this task. The Test Lab repository and its three existing images were left unchanged.
- Added `aws_ecr_repository.dcc_app` to the existing Terraform-managed configuration. The repository uses immutable tags, scan-on-push, AWS-managed AES256 encryption, and `force_delete = false`.
- `terraform fmt`: PASS. `terraform validate`: PASS.
- Reviewed plan: **1 to add, 0 to change, 0 to destroy**; the only planned resource was `aws_ecr_repository.dcc_app`. Applied only that saved plan: **1 added, 0 changed, 0 destroyed**.
- AWS verification: repository `dcc-app` exists in account `366314473733`; URI `366314473733.dkr.ecr.eu-north-1.amazonaws.com/dcc-app`; tag mutability `IMMUTABLE`; scan-on-push enabled; encryption `AES256`.
- Repository is empty (`list-images` returned `[]`). No image was built or pushed.
- Existing local Terraform state was preserved and now tracks the DCC repository alongside all existing Test Lab resources. No ECS, database, Redis, networking, security-group, or Cloud Map resources were changed.
- Final `terraform plan`: **No changes. Your infrastructure matches the configuration.**

**Task 48A status: PASS.** No image push or ECS deployment was performed.

## DCC image build and ECR publication - Task 48B

**Validation date:** 2026-10-26  
**AWS region:** `eu-north-1`  
**Result:** **PASS** (ECR scan findings pending)

- Backend regression suite: **137 tests passed**. Frontend `npm run typecheck` and `npm run build`: **PASS**.
- Built the root DCC `Dockerfile` for `linux/amd64`, tag `dcc-20261026-010107`. Local image ID and registry digest: `sha256:57ad794443ebb36b0b3409b2491aa985bd96d5b20da0fb96b6e5762e5a49510c`. ECR-reported image size: 74,221,176 bytes. Entrypoint: `sh /app/docker-entrypoint.sh` (Gunicorn defaults to one worker/four threads).
- Local loopback runtime: container remained running and became healthy; `/api/health/`, `/`, and referenced JS/CSS assets returned HTTP 200. No startup traceback or unhandled exception appeared.
- Content scan: **PASS**, 12,264 files checked. No environment files, Terraform state/plans, real private-key material, credentials, database/Redis secrets, or real Django secret keys were found. AWS SDK documentation example patterns and one invalid, non-key marker were identified and excluded as non-credentials.
- Published only `366314473733.dkr.ecr.eu-north-1.amazonaws.com/dcc-app:dcc-20261026-010107`. ECR confirms immutable repository tag, digest above, `linux/amd64` pull-back, and scan-on-push enabled.
- Removed the original local tag before pull-back. The registry pull returned the same SHA256 digest; the pulled container became healthy and `/api/health/` returned HTTP 200.
- **WARN:** `describe-image-scan-findings` returned `ScanNotFoundException`; no ECR scan findings are available yet although scan-on-push is enabled.
- Cleanup: both temporary validation containers and the local pushed-image tag were removed. The immutable ECR image remains.
- No ECS service/task definition change, Terraform operation/apply, or infrastructure deployment was performed.

**Task 48B status: PASS.** Image build, runtime, credential scan, ECR push, digest verification, and pull-back passed. ECR scan result remains pending.

## DCC non-root image correction - Task 49A

**Date:** 2026-10-26  
**Status:** **PASS**

- Replaced the prior root-default DCC image (`sha256:57ad794443ebb36b0b3409b2491aa985bd96d5b20da0fb96b6e5762e5a49510c`) with a rebuilt image that declares `USER 10001:10001`. A dedicated home and Gunicorn control-socket directory are writable by that UID/GID; application files remain read-only to the runtime user.
- Backend regression suite: **137 tests passed**. Frontend typecheck and production build: **PASS**.
- Built and pushed `366314473733.dkr.ecr.eu-north-1.amazonaws.com/dcc-app:dcc-20261026-021508` for `linux/amd64`.
- New immutable ECR digest: `sha256:cc2403f273f1ef120a668d7bf7c2b96743ffba4e27f00a588f5627a9047621e0` (ECR image size 74,225,641 bytes).
- Local runtime: **PASS**. Docker metadata reports user `10001:10001`; Gunicorn PID 1 UID/GID are both 10001. Container became healthy; `/api/health/`, `/`, and JS/CSS assets returned HTTP 200. No traceback or permission-denied errors.
- Content scan: **PASS**, 12,271 files checked. No environment files, Terraform state/plans, actual private-key material, AWS/database/Redis credentials, or real Django secret keys found. AWS SDK documentation examples and one invalid private-key marker were excluded as non-credentials.
- Pull-back: removed the local validation tag, pulled by the exact ECR digest, and verified matching image ID, `USER 10001:10001`, `amd64` architecture, healthy startup, HTTP 200 health/root/assets, and non-root Gunicorn process.
- Cleanup: temporary containers and local image were removed. The previous ECR image remains unchanged.
- Terraform and ECS were not modified; no infrastructure deployment was performed.

**Task 49A status: PASS.** The immutable non-root image is verified and available for a separately authorized ECS deployment.

## DCC ECS deployment attempt - Task 49B

**Date:** 2026-10-26  
**Status:** **BLOCKED — partial Terraform apply**

- Preflight passed: exact image digest `sha256:cc2403f273f1ef120a668d7bf7c2b96743ffba4e27f00a588f5627a9047621e0` exists in ECR; VPC `vpc-0b196d7bdefb910fc`, private application subnets, DCC control SG, and existing execution/task roles were present. No prior DCC ECS service or task definition existed. Test Lab API and Worker were 1/1; RDS and Redis were available.
- `terraform fmt` and `terraform validate` passed. Reviewed plan: **8 to add, 1 to change, 0 to destroy**. Actions were limited to DCC log group, DCC task definition/service, DCC private Cloud Map service, DCC Django secret, two diagnostic-only SG rules, and the existing ECS execution policy update for the DCC image/logs/secret.
- Apply created the DCC log group `/ecs/dcc-testlab/dcc-app`, task definition `dcc-app:1`, Cloud Map service `dcc-app`, dedicated Secrets Manager Django signing key, the two narrowly scoped diagnostic SG rules, and updated the existing ECS execution policy. The DCC ECS service was **not** created.
- **Blocker:** ECS rejected service creation because the service registry uses an A record while the Terraform service registry configuration also specifies `container_port`: `InvalidParameterException: The values specified for serviceRegistries do not require a value for 'containerPort'. Remove the value and retry.` No service/task is running for DCC. No retry or corrective apply was performed.
- Read-only post-failure checks confirmed the only ECS services remain Test Lab `api-service` and `worker-service`, each 1/1 running; RDS and Redis remain available. No temporary diagnostic task was launched.
- The generated Django secret is stored in Secrets Manager and in the local Terraform state as a sensitive value. Protect the local state accordingly. The temporary saved plan containing the secret was removed.
- No VPC, subnet, NAT, RDS, Redis, Test Lab service, or Test Lab Cloud Map service was changed. The non-root ECR image and prior DCC ECR image remain unchanged.
- Final `terraform plan`/`fmt -check` were **not run** after the partial apply, and no final no-change result is claimed.

**Task 49B status: BLOCKED.** Preserve the partial Terraform state and DCC resources. Resolve the Cloud Map A-record `container_port` configuration, then review a fresh plan before any further apply.

### Task 49B Cloud Map correction — plan only

**Date:** 2026-10-26  
**Status:** **READY FOR APPLY REVIEW; NOT APPLIED**

- Verified the existing DCC Cloud Map service is `dcc-app`, service ID `srv-bdp5hiigl5lgulvg`, in `dcc-test.internal`, with DNS record type `A`.
- Changed only the DCC ECS service `service_registries` block in `dcc_ecs.tf`: it now specifies the existing registry ARN and omits both `container_name` and `container_port`.
- `terraform fmt -check`: PASS. `terraform validate`: PASS.
- Fresh plan: **1 to add, 0 to change, 0 to destroy**. The sole action is `aws_ecs_service.dcc_app` creation as `dcc-app-service` in the existing `dcc-testlab-cluster`, desired count 1. It uses the existing task definition revision `dcc-app:1`, both private application subnets, DCC control SG `sg-06bf45d27e5bfb57f`, and public IP assignment disabled.
- Confirmed the preserved task definition still references image digest `sha256:cc2403f273f1ef120a668d7bf7c2b96743ffba4e27f00a588f5627a9047621e0`, user `10001:10001`, port 8000, existing DCC log group, and the Secrets Manager Django key.
- Existing DCC resources are preserved; the plan contains zero destroys. The temporary saved plan was removed after inspection.
- **No Terraform apply, manual ECS service creation, or smoke test was performed.** DCC ECS deployment remains incomplete until the reviewed plan is separately authorized for apply.

### Task 49D — DCC ECS service deployment and verification

**Deployment time:** 2026-10-26 02:37:31 +03:00 (task start)  
**Status:** **PASS — DCC service deployed privately**

- Pre-apply checks passed: `terraform fmt -check` and `terraform validate`. The fresh reviewed plan was **1 add, 0 change, 0 destroy**, with only `aws_ecs_service.dcc_app` to create. Terraform applied that reviewed plan.
- ECS cluster: `dcc-testlab-cluster`. Service: `dcc-app-service` (`arn:aws:ecs:eu-north-1:366314473733:service/dcc-testlab-cluster/dcc-app-service`), desired/running/pending `1/1/0`, deployment completed.
- Running task: `f2880f5700354fe889b9dbad22342043`, task definition `dcc-app:1`. The container is `RUNNING/HEALTHY`, with image digest `sha256:cc2403f273f1ef120a668d7bf7c2b96743ffba4e27f00a588f5627a9047621e0` and user `10001:10001`.
- Networking is private: application subnet `subnet-028c1d15210c04e4a`, DCC control SG `sg-06bf45d27e5bfb57f`, `assignPublicIp=DISABLED`, and no public IP.
- The task registered in the existing Cloud Map service `dcc-app` (`srv-bdp5hiigl5lgulvg`, namespace `dcc-test.internal`, A record); discovery returns the running task at private IP `10.80.37.217`. The instance attribute `AWS_INIT_HEALTH_STATUS` reports `UNHEALTHY` despite ECS reporting the task/container healthy and successful private HTTP checks. `get-instances-health-status` has no health-status records for this service; this remains a Cloud Map metadata/health-status limitation, not a claim that Cloud Map health is green.
- CloudWatch log group `/ecs/dcc-testlab/dcc-app` showed normal Gunicorn startup with no DCC startup traceback, permission error, missing-secret/configuration error, or database initialization failure.
- Private smoke tests: `/api/health/` **200**, `/` **200** (SPA HTML), a discovered JS asset **200**, and `/api/services/` **503** with a response (acceptable because AWS discovery is not configured for that runtime). Temporary diagnostic tasks were stopped after testing.
- Test Lab API and Worker remain `1/1`; RDS and Redis remain available.
- Final `terraform plan` reported **No changes**. No unrelated infrastructure was changed and no secret value was exposed.

**Task 49D status: COMPLETE.** DCC is running as a private ECS service; no DCC-to-Test-Lab integration work was performed.

## Task 50 — Complete Lab Redeploy and End-to-End Verification

**Date:** 2026-10-26  
**AWS account/region:** `366314473733` / `eu-north-1`  
**Status:** **PASS — complete existing lab stack redeployed and verified**

### Source and image verification

- Backend regression suite: **137 tests passed**.
- Frontend `npm run typecheck` and `npm run build`: **PASS**.
- Test Lab test suite: **22 tests passed**.
- Built/pushed immutable `linux/amd64` images. Both image configurations use UID/GID `10001:10001`.
- Test Lab tag `test-20261026-031204`, digest `sha256:8a620d72cd2824f75ed87bea3f9b3dff960dbbbe41a0ba2a50bb30f014294d40`.
- DCC tag `dcc-20261026-032757`, digest `sha256:549712cea4abc52cb8990a7d209febb9236d40df8eba1c167101aad23c0e83d7`.
- DCC live ECS discovery was corrected: the ECS API request no longer sends the unsupported `status` argument, and the DCC task role's read policy now permits the required scoped ECS discovery calls.

### Terraform and apply

- The existing local Terraform state was reused; no new state was initialized.
- Reviewed image/task-definition/service and IAM changes were applied through Terraform. No VPC, subnet, route/NAT, RDS, Redis, Cloud Map service/namespace, ECR repository, or unrelated SG replacement/destruction was performed.
- Final state contains **81 resources**.
- Final `terraform fmt -check -recursive`: **PASS**.
- Final `terraform validate -no-color`: **PASS**.
- Final `terraform plan -input=false -no-color`: **No changes. Your infrastructure matches the configuration.**

### ECS, data, and discovery

| Service | Task definition | Current task ID | Desired/running/pending | Result |
|---|---|---|---:|---|
| DCC `dcc-app-service` | `dcc-app:3` | `a87a679a82724237afc35ff628a81bd8` | `1/1/0` | `RUNNING/HEALTHY` |
| Test API `api-service` | `dcc-testlab-api:2` | `2ef8c846c6204edcb91c8ecb1b44467c` | `1/1/0` | `RUNNING/HEALTHY` |
| Test Worker `worker-service` | `dcc-testlab-worker:2` | `80f2a55c70e94069a11ef437e1753746` | `1/1/0` | `RUNNING`; ECS health `UNKNOWN` because no container health check is configured |

- DCC task definition pins the exact DCC digest above and specifies user `10001:10001`. Test API and Worker task definitions pin the exact Test Lab digest above; both images run as `10001:10001`.
- All three services use existing private application subnets, service-specific SGs, `assignPublicIp=DISABLED`, and task ENIs without public IPs.
- RDS PostgreSQL `dcc-testlab-postgres`: **available**, encrypted, private.
- Redis `dcc-testlab-redis`: **available**, encrypted at rest/in transit, private.
- Existing private Cloud Map namespace `dcc-test.internal` and services `dcc-app` / `dcc-test-api` have current task registrations. Cloud Map reports health metadata `UNKNOWN`; task health and actual private reachability were separately verified.

### Private smoke tests and logs

A one-off diagnostic Fargate task in the existing VPC was stopped after verification; no persistent diagnostic service was created.

| Check | Result |
|---|---|
| DCC `/api/health/`, `/`, discovered JS asset | **200 / 200 / 200** |
| DCC `/api/services/` | **200**, 3 ECS services discovered |
| Test API `/health`, `/ready`, `/metrics`, `/api/products`, `/api/orders` | **200** for each |
| Readiness PostgreSQL and Redis status | **available / available** |
| Redis write/readback | **PASS** |

Current DCC, API, and Worker task log streams were checked; no current startup traceback, permission/access-denied, Gunicorn, database, Redis, or secret/configuration error patterns were found. No secret values were printed or recorded.

### One-command deployment entry point

- Created [scripts/deploy-lab.ps1](../../../scripts/deploy-lab.ps1) and [ONE_COMMAND_DEPLOYMENT.md](../../../docs/deployment/ONE_COMMAND_DEPLOYMENT.md).
- The script reuses the current Terraform state, builds/pushes fresh immutable images, checks plan actions and requires explicit operator confirmation before applying the exact reviewed plan, then performs ECS/private health/dependency/final-plan checks.
- PowerShell parser and safety checks passed. The script was not run during this audit because doing so would trigger another image build and deployment.
- Next deployment command from the repository root: `.\scripts\deploy-lab.ps1`.

**Task 50 status: COMPLETE.** The complete existing lab stack is operational for the verified paths. No secret value was exposed.
