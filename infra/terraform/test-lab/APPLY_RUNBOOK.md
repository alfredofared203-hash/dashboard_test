# First Controlled AWS Apply Runbook

## Safety and scope

This is an operator runbook for a future, separately approved first deployment. It is not authorization to apply. Task 39 performs no AWS writes and must not run `terraform apply`, `terraform destroy`, or `terraform import`.

The Terraform stack deploys a network/IAM/ECR/Cloud Map foundation. It does **not** create ECS clusters, ECS services, task definitions, RDS, ElastiCache, or CloudWatch log groups.

Expected current plan: approximately **52 creates, 0 changes, 0 destroys**. Any changed count must be explained from a fresh reviewed plan.

## PHASE 0 — Preconditions

Do not proceed until every applicable item is confirmed and recorded without secrets:

1. **AWS identity:** `aws sts get-caller-identity --region eu-north-1`; verify the approved account and principal. Never paste credentials into this runbook.
2. **Region:** confirm `eu-north-1` is approved and matches `aws_region`/backend region.
3. **Terraform version:** run `terraform version`; require `>= 1.10.0, < 2.0.0`. Native S3 lockfiles require Terraform 1.10 or later.
4. **Credentials:** confirm the standard AWS credential chain/assumed role is approved and not expired. Do not print environment variables containing credentials.
5. **Backend bucket:** verify the externally bootstrapped bucket exists in the intended region, is private, versioned, encrypted, TLS-only, and has all S3 Block Public Access controls enabled. Verify the exact state prefix and access. Do not create the bucket here.
6. **IAM permissions:** have an authorized IAM reviewer confirm backend S3/KMS access and all create/read/tag permissions required by the exact Terraform plan. Include `iam:PassRole` only where the plan actually requires it. Do not test create permissions by attempting a write.
7. **Quotas:** verify required EC2 VPC/EIP/NAT, ECS/Fargate, ECR, Cloud Map, RDS, ElastiCache, and CloudWatch quotas against existing account usage. Request increases through the approved process before apply.
8. **Cost approval:** obtain explicit written cost approval for the one NAT Gateway/EIP and Cloud Map, and review [COST_REVIEW.md](./COST_REVIEW.md). Verify current regional prices.
9. **Architecture:** reconfirm one shared dedicated VPC, two AZs, six subnets, private DCC/Test Lab application tasks, private data tier, and no cross-VPC/public path between DCC and Test Lab.
10. **Repository/worktree:** inspect `git status --short` and branch/revision if Git is available. This workspace was not a Git repository at Task 39; if Git remains unavailable, record the source revision/worktree status by the approved release process and do not claim a clean tree.
11. **Artifacts:** verify no unexpected local state, saved plan, generated backend config, or user variable files exist. Preserve and review any state before continuing.

Any failed or unknown precondition is a stop condition.

## PHASE 1 — Backend

Backend setup is **not** performed automatically by Task 39. It is permitted only after the authorized bootstrap process has created and verified the S3 bucket.

1. Follow [BACKEND_BOOTSTRAP.md](./BACKEND_BOOTSTRAP.md).
2. Copy the inactive template into the stack root and create ignored `backend.hcl` locally. Insert the approved bucket name only in that ignored local file.
3. Confirm no state exists. If local state exists, stop and plan a separately authorized migration using `terraform init -migrate-state`; do not discard it.
4. After explicit authorization to initialize:

   ```powershell
   Set-Location infra\terraform\test-lab
   terraform init -reconfigure -backend-config=backend.hcl
   terraform workspace show
   terraform state list
   ```

5. Verify Terraform reports the S3 backend and the intended workspace/key. Confirm the initial state is empty and remote object access is scoped.
6. Verify native `.tflock` locking only through the controlled procedure in [BACKEND_BOOTSTRAP.md](./BACKEND_BOOTSTRAP.md). Do not use `-lock=false` for a remote backend.

Do not bootstrap S3, create a DynamoDB table, or initialize a remote backend as part of Task 39.

## PHASE 2 — Plan

From `infra\terraform\test-lab\`, after backend initialization is separately approved:

```powershell
terraform fmt -check -recursive
terraform validate -no-color
terraform plan -input=false -no-color
```

Inspect the entire plan, not just its summary:

- Verify account, region, CIDRs, AZs, subnet roles, route associations, NAT placement, IAM actions, SG rules, and all resource names/tags.
- Expected baseline is approximately **52 resources** unless repository changes have a legitimate, reviewed explanation.
- Verify data subnets have no IGW/NAT default route, application subnets use the single NAT route, and no DCC/Test API public ingress or public task IP is planned.
- Verify no unexpected destroy, replacement (`-/+`), external data mutation, or unknown high-risk action.
- If anything is unexpected, stop and revise/review the plan.

Do not save a plan unless an authorized reviewer explicitly approves doing so. If approved, generate the exact artifact to be applied and inspect it:

```powershell
terraform plan -input=false -out=tfplan
terraform show -no-color tfplan
```

Saved plan files may contain sensitive values; keep them local, protected, and ignored by Git. Do not share them or commit them.

## PHASE 3 — Human approval gate

Require explicit human approval of:

- The exact AWS account and region.
- The exact fresh plan output and resource count.
- The backend bucket, workspace, and lock behavior.
- CIDR/network and security-group review.
- IAM/quotas and written cost approval.

If a saved plan is used, approval must identify that exact `tfplan` artifact (for example by a securely recorded hash). Any configuration or plan change invalidates approval and requires a new plan and review. No automation or agent may infer approval from a successful plan.

## PHASE 4 — Apply

Only after Phase 3 approval, from the initialized stack directory:

```powershell
terraform apply -input=false tfplan
```

This command is for the approved saved plan only. If no saved plan was explicitly authorized, stop and obtain approval for the exact apply procedure; do not apply an unreviewed fresh plan. Do not use `-auto-approve`.

## PHASE 5 — Post-apply verification

Capture identifiers and verify them read-only against Terraform state and AWS APIs:

- VPC exists with the approved CIDR, DNS support, and DNS hostnames.
- Exactly two approved AZs and six subnets exist: two public, two private application, and two private data.
- Each subnet is associated with the expected route table. Public default routing targets the IGW; application default routing targets the single NAT; data subnets have no Internet/NAT default route.
- Exactly one IGW and one NAT Gateway/EIP exist and are available.
- All six SGs exist in the same VPC; ingress/egress match the reviewed SG matrix, with no public ingress and no all-to-all rules.
- ECR repository and lifecycle policy exist with intended immutable tags/scanning/encryption.
- Cloud Map private namespace/service definition exist and are associated with the VPC.
- IAM roles and execution policy have the intended trust and least-privilege statements.
- Inspect ECS inventory and report readiness only. **This Terraform stack does not create ECS clusters, services, or task definitions.** No ECS service should be claimed as created by this apply.
- RDS, ElastiCache, and CloudWatch log groups are outside the current stack and must not be reported as created.

Retain Terraform outputs, plan, apply logs, and identifiers only in approved protected records; do not include credentials or state contents.

## PHASE 6 — Rollback and recovery

- **Plan unexpectedly contains destroy/replacement:** do not apply. Preserve the plan, inspect state/config/provider changes, and obtain a revised independent review.
- **Apply partially fails:** do not rerun blindly and do not destroy the environment. Read the error, inspect state and the actual AWS resource inventory, identify completed and failed actions, then produce a new reviewed plan. Contact the platform owner if state/resource ownership is unclear.
- **NAT creation fails:** stop dependent deployment. Check service health, EIP/NAT quota, subnet/route prerequisites, and the exact AWS error. Do not expose private tasks publicly as a workaround. Re-plan after the approved correction.
- **IAM creation fails:** stop. Have the IAM owner review the denied action and trust/policy scope; do not attach administrator policies or broaden permissions without approval.
- **State lock is held:** identify the owning process and exact lock metadata. Wait for active work to finish. Force-unlock only after confirming no operation remains active, obtaining state-owner approval, and confirming the exact lock ID, as described in [BACKEND_BOOTSTRAP.md](./BACKEND_BOOTSTRAP.md). Never manually delete a lock object.
- **AWS quota is exceeded:** stop and request an approved quota increase, or obtain a reviewed plan change. Do not retry loops or change architecture without approval.
- **Resource cleanup is required:** assess resource/data retention and create a separately reviewed teardown plan with explicit approval. Never recommend blindly running `terraform destroy`.

## Current Task 39 boundary

Task 39 is preparation only. No AWS write operation, apply, destroy, import, or backend initialization is allowed under this runbook.
