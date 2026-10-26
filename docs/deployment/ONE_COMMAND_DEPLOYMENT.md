# One-command lab deployment

This workflow redeploys the existing DCC + Test Lab stack in AWS account
`366314473733`, region `eu-north-1`. It reuses the Terraform state in
`infra/terraform/test-lab`; it is not a greenfield bootstrap and must not be
run from a fresh or different Terraform workspace.

## Prerequisites

- Windows PowerShell 5.1 or later.
- AWS CLI authenticated as an operator allowed to read the existing stack,
  push to both ECR repositories, apply the reviewed Terraform changes, and
  launch/inspect an on-demand private smoke-test task.
- Terraform and Docker Desktop with the Linux engine and `buildx`.
- Node.js/npm and Python available on `PATH`.
- Backend and Test Lab development dependencies installed. If present, the
  script uses `backend\.venv` and `test-app\.venv`; otherwise it uses `python`
  from `PATH`. Frontend `node_modules` must be installed for `npm run`.
- The existing local Terraform state and configuration in this checkout.
  Preserve the state files; the script refuses to proceed if expected stack
  resources are absent.

## Run

From the repository root:

```powershell
.\scripts\deploy-lab.ps1
```

The script verifies the AWS account and region, formats/validates Terraform,
then runs the backend tests, frontend typecheck/build, and Test Lab tests. It
builds both images for `linux/amd64`, checks the non-root image user, scans the
application image filesystems for environment files, Terraform state/plans,
private-key markers, and AWS access-key patterns, pushes new timestamped
immutable tags, and resolves the exact ECR digests.

It obtains the existing DCC signing key from Secrets Manager into a temporary
process environment variable for Terraform. It does not print, replace, or
rotate that key. The temporary Terraform plan and smoke-test request file are
kept under the Windows temporary directory and removed on exit; sensitive
environment variables are cleared in the script's `finally` block.

Before applying, the script prints the complete Terraform plan and checks its
JSON actions. It permits image-driven task-definition revisions and updates to
the three ECS services (plus an in-place DCC discovery policy update); it
rejects unrelated changes and all other destructive actions. It then asks for
the exact word `APPLY` and applies only that reviewed saved plan. It never runs
`terraform destroy` and does not use `-auto-approve`.

After apply, it waits for ECS stability; checks all three services are 1/1/0,
the pinned image digests and DCC container user, private application subnets,
security groups, and absence of public task IPs; verifies RDS, Redis, and
Cloud Map; runs private HTTP/database/cache smoke checks; checks current task
logs; and requires the final Terraform plan to report `No changes`.

The private smoke test launches one temporary Fargate task from the existing
Test API task definition in the existing VPC and stops it after completion.
Its Redis check uses a temporary unique key and deletes that key afterward.
Cloud Map health metadata may remain `UNKNOWN`; ECS task health and actual
private registration/reachability are checked separately.

## Expected final output

Successful completion ends with:

```text
PASS: deployment complete; all services, dependencies, private smoke checks, logs, and final Terraform plan verified.
```

The run also prints each immutable image digest, service check, and endpoint
HTTP status. A failure stops the workflow; do not interpret a partial run as
a completed deployment.

## Verify the applications

The script's private diagnostic task verifies:

- DCC: `/api/health/`, `/`, a discovered static JS/CSS asset, and
  `/api/services/`.
- Test Lab: `/health`, `/ready`, `/metrics`, `/api/products`, and
  `/api/orders`.
- PostgreSQL and Redis availability via `/ready`; Redis unique-key
  write/read/delete.

For a manual AWS-side check, use ECS service status in cluster
`dcc-testlab-cluster` and inspect the private CloudWatch log groups:

- `/ecs/dcc-testlab/dcc-app`
- `/ecs/dcc-testlab/api`
- `/ecs/dcc-testlab/worker`

The application URLs are private Cloud Map names, not public endpoints:
`dcc-app.dcc-test.internal` and `dcc-test-api.dcc-test.internal`.

## Troubleshooting

- **Wrong AWS account:** authenticate to account `366314473733`, then retry.
- **Missing Terraform state:** stop. Restore the original local state/workspace;
  do not initialize a new state or import/recreate resources as a workaround.
- **Missing dependencies:** install the repository's documented backend,
  frontend, and Test Lab development dependencies, then rerun.
- **ECR push/build failure:** verify Docker Desktop is using Linux containers,
  `buildx` supports `linux/amd64`, and the identity can push to both existing
  repositories.
- **Plan rejected:** review the listed actions. The script deliberately stops
  for unexpected or destructive infrastructure changes; do not bypass its
  checks or apply the plan manually without reviewing the difference.
- **ECS task or smoke check fails:** inspect the relevant task's stopped reason,
  current task CloudWatch stream, and service events. The script stops a
  still-running smoke task during cleanup after an error.
- **Final plan is not clean:** inspect Terraform drift and input values. Do not
  run another apply automatically.

## Deployment order and scope

The current Terraform root is monolithic and manages the existing network,
security, IAM, ECR, Cloud Map, database/cache, and ECS resources together.
The script deliberately reuses that root and state rather than trying to
split it with `terraform -target`. For the existing lab the workflow is:

1. Verify prerequisites, AWS identity, and the existing Terraform state.
2. Terraform init, format, and validation.
3. Backend tests; frontend typecheck/build; Test Lab tests.
4. Build/test-validate and push the Test Lab image; capture its ECR digest.
5. Build/test-validate and push the DCC image; capture its ECR digest.
6. Create, inspect, and explicitly approve a constrained Terraform plan.
7. Apply that exact plan; wait for ECS stability.
8. Verify networking, image digests, RDS/Redis, Cloud Map, logs, and private
   application paths.
9. Require a final Terraform plan of `No changes`.

Foundation/data provisioning is not a separate automatic stage because the
existing stack is already deployed and the root is not divided into stage
roots. Do not use this redeploy workflow as a substitute for a separately
reviewed first-time infrastructure bootstrap.
