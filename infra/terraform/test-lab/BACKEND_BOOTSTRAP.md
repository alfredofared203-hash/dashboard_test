# Terraform Remote Backend Bootstrap Runbook

## Scope and current status

This runbook describes prerequisites for a future, separately authorized remote-state bootstrap. It does **not** create the S3 bucket, a lock table, IAM identities, or AWS resources.

The active Test Lab stack currently uses Terraform's default local backend: there is no `backend.tf` at the stack root. `backend-template/backend.tf` is an intentionally inactive template; `backend.s3.example.hcl` contains only non-secret example values. The backend uses Terraform's native S3 lockfile (`use_lockfile = true`) and does not require DynamoDB. Terraform must be `>= 1.10.0, < 2.0.0`; the AWS provider is constrained to `~> 6.0` and locked to `6.70.0`.

No local Terraform state or saved plan file was found during Task 39's workspace scan. The workspace has no `.git` metadata, so tracked/committed status cannot be verified here.

## Bucket requirements

An authorized platform/bootstrap process must provision and approve a dedicated bucket before remote initialization. Do not infer or invent a bucket name; the real bucket name must be supplied by its owner through the ignored local backend configuration.

The bucket must:

- Be private, with all four S3 Block Public Access settings enabled.
- Have versioning enabled before Terraform state is stored.
- Enforce server-side encryption at rest (SSE-S3 or an approved SSE-KMS key). If SSE-KMS is selected, grant the deployment identity only the required key permissions and scope them to that key.
- Enforce TLS-only access through the bucket policy, and use bucket-owner-enforced object ownership.
- Be in the approved region and dedicated to protected infrastructure state. The example key is `dcc/test-lab/terraform.tfstate`.
- Preserve object versions according to the organization's recovery policy; do not apply a lifecycle rule that prematurely expires current state or required recovery versions.
- Have access logging/monitoring enabled where required by the platform's controls.

## Least-privilege IAM requirements

The deployment identity needs state-backend access in addition to separately reviewed permissions for the Terraform resources in the plan. Backend permissions are not supplied by the AWS provider's infrastructure policy.

Scope permissions to the approved bucket and the exact state prefix/key:

| Action | Resource | Purpose |
|---|---|---|
| `s3:ListBucket` | Bucket ARN, constrained to the state prefix where practical | Locate the configured state/lock objects |
| `s3:GetObject`, `s3:PutObject` | Exact state object key | Read/write Terraform state |
| `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject` | Exact state lock object key ending in `.tflock` | Acquire, update, and release Terraform's native S3 lock |

Do not grant bucket-wide object access, public access, or permission to change bucket policy/versioning as part of routine deployment access. If SSE-KMS is used, add only the necessary `kms:Encrypt`, `kms:Decrypt`, and `kms:GenerateDataKey` permissions on the approved key; validate exact requirements with the key policy and AWS documentation. The platform bootstrap identity and Terraform deployment identity should be distinct where feasible.

No DynamoDB table or DynamoDB lock permissions are needed for the selected native lockfile design.

## Non-secret backend configuration

The stack template is intentionally kept outside the stack root so local planning does not require a bucket. After bootstrap approval, an operator may prepare the local configuration:

```powershell
Set-Location infra\terraform\test-lab
Copy-Item backend-template\backend.tf backend.tf
Copy-Item backend.s3.example.hcl backend.hcl
```

Edit only the ignored `backend.hcl` locally to replace the bucket placeholder with the real, approved bucket name. Keep the region, key, and encryption setting aligned with the approved platform decision. `use_lockfile = true` is declared in `backend-template/backend.tf`; do not add a DynamoDB backend lock table.

Backend files must not contain credentials. Use the standard AWS credential chain or an approved assumed role, never access keys in backend HCL.

## Initialization after authorized bootstrap

Before initialization, confirm the bucket controls, IAM access, region, backend key, Terraform version, and whether any local state exists.

For the current no-state condition, from the stack directory:

```powershell
terraform init -reconfigure -backend-config=backend.hcl
terraform workspace show
terraform state list
```

Verify that initialization identifies the S3 backend and that `terraform state list` is empty before the first apply. Do not use this sequence to discard or overwrite existing state.

If a local state appears before migration, stop. Back it up in an approved protected location, inspect it without publishing it, and obtain separate authorization to migrate it. Use Terraform's `terraform init -migrate-state -backend-config=backend.hcl` only for a reviewed migration; do not substitute `-reconfigure` when state must be preserved.

## Verify locking safely

After remote initialization is approved, verify the configured S3 lockfile behavior during a controlled maintenance window using two authorized Terraform processes pointed at the same workspace/key:

1. Start a normal `terraform plan` in process A and confirm it holds the backend lock while running.
2. While A holds the lock, run `terraform plan -lock-timeout=10s` in process B. Confirm B waits and then reports a lock timeout rather than proceeding concurrently.
3. Let A finish normally; verify B can then acquire and release the lock on a later plan.
4. Do not run concurrent applies or intentionally interrupt an apply to test locking.

The Task 39 local plan uses `-lock=false` only because the active configuration has no remote backend and no local state. That flag is not appropriate for normal remote-backend operations.

## Recover a stale lock

Never remove a `.tflock` object or run `terraform force-unlock` merely because a lock is old.

1. Stop and identify all Terraform processes/automation using the exact backend, key, and workspace.
2. Confirm with the operator who initiated the lock that no plan/apply is active and inspect the lock ID and operation metadata from Terraform's error output.
3. Confirm the state object and recent S3 object version are present. Preserve evidence and notify the backend/state owner.
4. Obtain explicit approval from the state owner for the exact lock ID.
5. Only then use `terraform force-unlock <LOCK_ID>` from the initialized stack directory. Do not use `-force` to bypass the confirmation prompt unless separately authorized.
6. Re-run a normal locked plan and compare the state to the last approved inventory before any apply.

Manual deletion of lock objects, editing state, or blind force-unlock can corrupt or race state and is prohibited.

## Never commit

Never commit:

- AWS access keys, secret keys, session tokens, private keys, passwords, database credentials, or secret values.
- Real backend credentials/configuration, including the ignored `backend.hcl`; do not commit the real bucket name/key if platform policy treats them as internal metadata.
- Terraform state or state backups (`*.tfstate*`), saved plans (`*.tfplan*`), or crash logs, which can contain sensitive infrastructure data.
- User-specific `terraform.tfvars` or generated `.terraform` contents.

The checked-in backend template and example HCL are safe placeholders. The AWS provider lock file is not a credential and should remain committed.
