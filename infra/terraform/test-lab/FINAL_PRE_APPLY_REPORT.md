# Final Pre-Apply Report

**Report date:** 2026-10-25  
**AWS inspection region:** `eu-north-1`  
**Task:** 39 — final pre-apply readiness gate  
**AWS resources created/modified/deleted by Task 39: NONE**

## Architecture

- **DCC + Test Lab = same dedicated VPC.**
- **2 AZs**: `eu-north-1a`, `eu-north-1b`.
- **6 subnets**: 2 public, 2 private application, 2 private data.
- DCC ECS tasks, Test API ECS tasks, Test Worker ECS tasks, and diagnostic tasks are intended for the **private application tier**, with `awsvpc` and public IP assignment disabled.
- RDS/Redis are intended for the **private data tier**; data subnets have no Internet/NAT default route.
- The foundation plans **one NAT Gateway** in the first public subnet; both private application subnets route egress through it. It is a single-AZ dependency and meaningful recurring lab cost.
- **No cross-VPC networking**: no peering, Transit Gateway, VPN, PrivateLink, or public connectivity between DCC and Test Lab. DCC runtime VPC: **will be created by the approved Test Lab/DCC deployment architecture.**
- Terraform creates network, SG, IAM, ECR, and Cloud Map foundation resources only. It does **not** create ECS clusters/services/task definitions, RDS, ElastiCache, or CloudWatch log groups.

## Terraform

| Check | Result |
|---|---|
| Terraform version | `1.15.8`; satisfies `>= 1.10.0, < 2.0.0` |
| AWS provider | Constraint `~> 6.0`; lockfile version `6.70.0` |
| `terraform fmt -check -recursive` | PASS |
| `terraform validate -no-color` | PASS |
| Valid default CIDR plan | PASS |
| Overlapping subnet negative test | PASS — planning rejected at the VPC precondition |
| Subnet outside VPC negative test | PASS — planning rejected at the VPC precondition |
| Final read-only plan | **52 to add, 0 to change, 0 to destroy** |
| Destroy actions | **0** |
| Replacement actions | **0** |
| Plan errors | **0** |

The plan was run locally with `-lock=false` because the active stack has no remote backend or local state. This does not validate remote locking and is not an approved remote-backend operating mode. The final plan output remains a local, uncommitted review artifact.

## AWS Read-Only Checks

AWS CLI identity and read operations succeeded using the configured credential chain. No credentials were printed or changed.

| Area | Read access | Observed result |
|---|---|---|
| STS identity | Verified | IAM user principal; account identity confirmed in the CLI session. AWS region was not set in region environment variables; explicit inspection region `eu-north-1` was used. |
| EC2 network | Verified | One visible VPC: default `172.31.0.0/16`; three public-IP-on-launch subnets in `eu-north-1a/b/c`; main route table has local route and default route to attached IGW. No NAT gateway or allocated EIP was returned. The planned `10.80.0.0/16` does not overlap the visible regional VPC/subnets. |
| Peering/TGW/VPN | Verified | No VPC peering, Transit Gateway VPC attachment, VPN gateway, VPN connection, or Client VPN endpoint returned. |
| ECS | Verified | No ECS clusters returned. |
| ECR | Verified | No repositories returned. |
| Cloud Map | Verified | No namespaces or services returned. |
| RDS | Verified | No DB instances or DB subnet groups returned. |
| ElastiCache | Verified | No cache clusters or cache subnet groups returned. |
| CloudWatch | Verified | Logs API and metrics API readable; no log groups, ECS metrics, or alarms returned. |
| IAM | Partial read verified | IAM role/user-policy reads succeeded. These reads do not establish create permissions or effective permissions after boundaries/SCPs. |

### Permissions and quota matrix

| Area | Read access verified | Create permission verified | Quota verified | Status |
|---|---|---|---|---|
| EC2/VPC, routes, SG, NAT/EIP | YES | NOT VERIFIED — requires authorized IAM review | EIP quota reported as 5; no EIPs currently allocated. NAT-specific quota not returned in the queried result. | Read-only review passed; apply access unknown |
| ECS/Fargate | YES | NOT VERIFIED — requires authorized IAM review | Fargate On-Demand vCPU quota reported as 12; ECS cluster/service-specific quotas not returned. No clusters exist. | Future ECS deployment not included in this Terraform plan |
| ECR | YES | NOT VERIFIED — requires authorized IAM review | Repository quota not returned. | No repository exists |
| Cloud Map | YES | NOT VERIFIED — requires authorized IAM review | Relevant namespace/service quota not verified. | No namespace exists |
| RDS | YES | NOT VERIFIED — requires authorized IAM review | DB instances quota reported as 40; no instances exist. | RDS not included in this Terraform plan |
| ElastiCache | YES | NOT VERIFIED — requires authorized IAM review | Cache quota not returned. | ElastiCache not included in this Terraform plan |
| CloudWatch Logs | YES | NOT VERIFIED — requires authorized IAM review | Log groups quota reported as 1,000,000; no log groups exist. | Log groups not included in this Terraform plan |
| S3 backend | Not verified | NOT VERIFIED — requires authorized bootstrap/IAM review | Not verified | Bucket does not exist in this stack and is not created by Task 39 |

Service Quotas API did not return every product quota queried. Reported values are read-only observations, not an approval or a proof of available headroom for other resources. No write was attempted to test authorization.

## Backend / State

- **Active backend:** default local backend; no root `backend.tf`.
- **Template:** `backend-template/backend.tf` is inactive and declares native S3 locking with `use_lockfile = true`.
- **Example values:** `backend.s3.example.hcl` uses a placeholder bucket name, a state key, `eu-north-1`, and encryption. It contains no credentials. No actual bucket name is defined in the repository.
- **Terraform version / locking:** Terraform `1.15.8`; native S3 lockfile support is compatible with the declared minimum `1.10.0`. No DynamoDB lock table is required.
- **State / plan artifacts:** zero `terraform.tfstate*` and zero saved `*.tfplan*` artifacts found in the workspace scan.
- **Backend bootstrap requirements:** private S3 bucket; versioning, encryption, public access block, TLS-only policy, least-privilege state and `.tflock` access; details in [BACKEND_BOOTSTRAP.md](./BACKEND_BOOTSTRAP.md).
- **Backend readiness:** **NOT READY** — no approved/provisioned bucket or IAM access is established. Do not initialize a remote backend until an authorized bootstrap process completes.
- Workspace has no `.git` metadata, so tracked/committed status cannot be independently verified.

## Security

### Security group review

| Source | Destination | Port/protocol | Direction | Purpose |
|---|---|---|---|---|
| DCC control SG | Test API SG | TCP 8080 | DCC egress / API ingress | Same-VPC DCC-to-Test-API communication |
| Diagnostic worker SG | Test API SG | TCP 8080 | Worker egress / API ingress | Target task diagnostics |
| Test API SG | RDS SG | TCP 5432 | API egress / RDS ingress | PostgreSQL |
| Test Worker SG | RDS SG | TCP 5432 | Worker egress / RDS ingress | PostgreSQL |
| Test API SG | Redis SG | TCP 6379 | API egress / Redis ingress | Redis/Valkey |
| Test Worker SG | Redis SG | TCP 6379 | Worker egress / Redis ingress | Redis/Valkey |
| DCC, diagnostic worker, Test API, Test Worker SGs | `0.0.0.0/0` | TCP 443 | Egress only | HTTPS egress through private-app NAT route |

DCC control SG has no ingress rules. PostgreSQL/Redis ingress is SG-scoped; no public inbound or all-to-all rule is planned. HTTPS egress is destination-broad, but outbound only. No ECS task has a public IP in the planned subnet definitions. The Test API and DCC services must be deployed to private application subnets and attach their corresponding SGs.

### Secret/artifact audit

Repository scan results (values withheld):

| Category | Result | Path / note | Remediation |
|---|---|---|---|
| AWS access-key ID patterns | NOT FOUND | Source/configuration scan, excluding dependency/build caches | Continue using credential chain; never commit keys |
| AWS secret-key patterns | NOT FOUND | Source/configuration scan | Never store credentials in Terraform or documentation |
| GitHub/private token patterns | NOT FOUND | Source/configuration scan | Continue secret scanning before release |
| Private-key PEM markers | NOT FOUND | Source/configuration scan | Keep private keys outside repository |
| Password-like example | FOUND — placeholder only | `test-app/.env.example`; example file is ignored by the root Git ignore rules | Keep real `.env` local and never commit; no literal credential identified |
| Database password references | FOUND — configuration references only | Test Lab application config/compose and README; values are runtime/env references, not AWS credentials | Supply secrets locally/through approved secret manager; never use committed values |
| Backend credential assignments | NOT FOUND in backend files | Backend template/example contain no access keys, passwords, or tokens | Keep real backend config ignored and credential-free |
| Terraform state files | NOT FOUND | No `terraform.tfstate*` files found | Preserve `.gitignore` rules |
| Saved Terraform plan files | NOT FOUND | No `*.tfplan*` files found | Keep saved plans protected and uncommitted |

The repository is not a Git worktree in this environment, so this scan cannot prove what is present in Git history or a remote repository.

## Cost

- [COST_REVIEW.md](./COST_REVIEW.md): **created and reviewed against resources in the current Terraform plan**.
- Cost approval required: **YES**.
- Cost approval status: **NOT CONFIRMED**.
- Recurring baseline includes one NAT Gateway and its public IPv4/EIP, plus the Cloud Map private namespace. NAT data processing and cross-AZ egress can add usage cost. ECR becomes storage/transfer-dependent after image push.
- One-NAT design retained: **YES**; meaningful lab cost and single-AZ egress dependency. Current prices require verification before apply.
- ECS/Fargate, RDS, ElastiCache, and CloudWatch log groups are not in the current plan and are not included as current baseline resources.

## Application Regression

| Project | Result |
|---|---|
| DCC backend | PASS — `manage.py check` clean; 137 tests passed |
| Frontend | PASS — `npm run typecheck` and `npm run build` |
| Test Lab | PASS — 22 tests passed; one upstream AnyIO deprecation warning |

## Remaining Blockers

1. Remote S3 backend bucket has not been provisioned/approved; state access and locking have not been verified.
2. Cost approval is not confirmed; verify current regional AWS prices.
3. Required create permissions and effective IAM policy remain **NOT VERIFIED — requires authorized IAM review**.
4. Quota coverage is partial; ECS/ECR/Cloud Map/ElastiCache and NAT-specific quotas/headroom are not all verified.
5. `APPLY_RUNBOOK.md` documents the required sequence but does not authorize an apply.
6. No Git metadata is available, so clean/known repository state and committed-history secret audit cannot be asserted.

## Final Status

**NOT READY FOR CONTROLLED AWS APPLY**

AWS resources created/modified/deleted by Task 39: **NONE**.
