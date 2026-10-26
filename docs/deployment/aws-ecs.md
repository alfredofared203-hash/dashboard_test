# AWS ECS Deployment Guide

This document describes the current DCC production deployment contract for ECS without committing any production secrets or credentials.

For the separate, disposable target environment used to validate DCC against real ECS workloads, see the [AWS Test Laboratory Blueprint](./aws-test-lab.md). The lab is intentionally not the DCC production service or a deployment of the DCC itself as a diagnostic target.

## Deployment model

DCC deploys as a single ECS application task with a single container named `dcc`.

- one ECR repository for the DCC image
- one image tag per immutable revision
- one ECS task definition
- one ECS service
- one application container
- same-origin frontend + backend runtime

The application may also launch short-lived diagnostic ECS tasks through the existing backend diagnostic provider, but those are separate from the long-lived DCC application task and are not a sidecar or second application container.

## Required AWS context

Before provisioning or updating AWS resources, identify the active account, region, VPC, subnets, security groups, cluster, and any existing approved ingress. The repository does not store credentials; it expects the standard AWS CLI credential chain or a task role provided by ECS.

The deployment should record the following without printing secrets:

- AWS account ID (non-secret identifier)
- AWS region
- target ECS cluster
- target VPC
- target subnets
- target security group
- image URI
- task definition ARN
- ECS service ARN

## ECR

Use an existing ECR repository if the environment already has one. If none exists, create a single repository for the DCC application image and tag it with an immutable revision such as:

```text
dcc:<git-sha>
```

Avoid using `latest` as the only rollback reference. `latest` may be used as a convenience label, but the deployment record should always retain the immutable revision identifier used by the service.

## ECS task definition

A production task definition should include the following minimum configuration:

```json
{
  "family": "dcc-production",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "containerDefinitions": [
    {
      "name": "dcc",
      "image": "<account>.dkr.ecr.<region>.amazonaws.com/dcc:<git-sha>",
      "essential": true,
      "portMappings": [{ "containerPort": 8000, "hostPort": 8000, "protocol": "tcp" }],
      "healthCheck": {
        "command": ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health/', timeout=5)\""],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 20
      },
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/dcc/production",
          "awslogs-region": "<region>",
          "awslogs-stream-prefix": "dcc"
        }
      },
      "environment": [
        { "name": "DJANGO_DEBUG", "value": "false" },
        { "name": "PORT", "value": "8000" },
        { "name": "AWS_REGION", "value": "<region>" },
        { "name": "DCC_ECS_CLUSTERS", "value": "<existing-workload-cluster-name-or-arn>" },
        { "name": "DCC_DIAGNOSTIC_PROVIDER", "value": "ecs" },
        { "name": "DCC_ECS_CLUSTER", "value": "<diagnostic-worker-cluster-name-or-arn>" },
        { "name": "DCC_ECS_TASK_DEFINITION", "value": "<diagnostic-worker-task-definition>" },
        { "name": "DCC_ECS_SUBNETS", "value": "<same-vpc-private-application-subnet-id-1>,<same-vpc-private-application-subnet-id-2>" },
        { "name": "DCC_ECS_SECURITY_GROUPS", "value": "<diagnostic-worker-security-group-id>" },
        { "name": "DCC_ECS_CONTAINER_NAME", "value": "<diagnostic-worker-container-name>" },
        { "name": "DCC_METRICS_PROVIDER", "value": "cloudwatch" },
        { "name": "DCC_CLOUDWATCH_REGION", "value": "<region>" },
        { "name": "DCC_CLOUDWATCH_CLUSTER_NAME", "value": "<existing-workload-cluster-name>" },
        { "name": "DCC_CLOUDWATCH_SERVICE_NAME", "value": "<existing-workload-service-name>" },
        { "name": "DCC_CLOUDWATCH_ECS_NAMESPACE", "value": "AWS/ECS" },
        { "name": "DCC_CLOUDWATCH_CONTAINER_INSIGHTS_NAMESPACE", "value": "ECS/ContainerInsights" },
        { "name": "DCC_LOGS_PROVIDER", "value": "loki" },
        { "name": "DCC_LOKI_URL", "value": "https://loki.example.internal" },
        { "name": "DCC_DEPENDENCIES_PROVIDER", "value": "cloudwatch" }
      ]
    }
  ]
}
```

The exact values should match the environment and enabled providers. Sensitive values such as `DJANGO_SECRET_KEY` should be injected through AWS Secrets Manager or another approved native secret mechanism, not as plaintext environment variables.

## IAM

### Execution role

The ECS execution role must be scoped to only the permissions needed to:

- pull the image from ECR
- write logs to CloudWatch Logs
- retrieve secrets if configured

It must not be an admin or broadly privileged role.

### Task role

The DCC application task role is used by Django/boto3 for ECS discovery, CloudWatch, and enabled observability calls. For each explicitly configured discovery cluster, allow only:

- `ecs:DescribeClusters`
- `ecs:ListServices` and `ecs:DescribeServices`
- `ecs:ListTasks` and `ecs:DescribeTasks`
- `ecs:DescribeTaskDefinition`

The provider requests only configured clusters and currently running tasks. Scope resource-level ECS permissions where supported and verify `DescribeClusters`/list-action resource requirements against the AWS service authorization reference.

When `DCC_DIAGNOSTIC_PROVIDER=ecs`, add only the required `ecs:RunTask`, `ecs:StopTask`, and narrowly scoped `iam:PassRole` permissions for the configured worker task definition and roles. The DCC application and diagnostic worker may need distinct task roles. Keep metrics and log permissions restricted to configured resources.

Do not grant broad `iam:*`, `ec2:*`, or unrelated mutation permissions.

## Security group and networking

Use an application-specific security group with only the required ports exposed.

Recommended posture:

- allow inbound traffic to port `8000` only from the approved ingress source
- do not expose SSH, database ports, Redis ports, debug ports, or dev ports
- restrict outbound access to the AWS APIs and external endpoints required by the configuration

The application should run in the existing approved VPC and only in approved subnets. Prefer private subnets where the environment supports the route to ECR, CloudWatch Logs, and required AWS endpoints.

For the approved Test Lab deployment, DCC is not placed in a separate existing VPC: the DCC ECS service and Test Lab services use the same dedicated VPC and private application subnets from the Test Lab Terraform outputs. Attach the `dcc_control` SG to the DCC service, set `assignPublicIp=DISABLED`, and keep its private API egress limited to the Test API SG/port. The on-demand diagnostic task uses the same subnet outputs with the separate `diagnostic_worker` SG. This arrangement requires no peering, Transit Gateway, VPN, PrivateLink, or public connectivity between DCC and the Test Lab. Operator ingress to DCC remains a separate private concern.

## HTTPS and ingress

Production browser traffic must use HTTPS.

Use a load balancer or equivalent TLS ingress when available. If no HTTPS ingress is configured, report the blocker rather than weakening Django security settings or exposing the service over plain HTTP in production.

The app must keep:

- `DJANGO_DEBUG=false`
- explicit HTTPS `DCC_CORS_ALLOWED_ORIGINS`
- no browser credential cookies or CSRF login flow
- proxy-aware HTTPS/security settings

DCC has no application authentication or user accounts. Restrict the service at the network ingress and do not rely on CORS as an access-control mechanism.

## Health checks and rollout

ECS health checks should call:

```text
GET /api/health/
```

This endpoint is lightweight and unauthenticated, so it is appropriate for service readiness. Keep container health checks separate from expensive optional providers such as CloudWatch/Prometheus/Loki. Optional observability failures should not make the service unhealthy unless the app itself is failing.

Use a single service with desired count `1` for the initial deployment. The DCC diagnostic and rate-limit state is process-local, so multiple tasks do not share state and should not be used without explicit architectural approval.

## Real ECS discovery smoke test

After the task role, region, and explicit `DCC_ECS_CLUSTERS` values are configured, validate read-only discovery before enabling diagnostic execution:

1. Call `GET /api/ecs/clusters/` and confirm only the configured clusters appear with live status.
2. For each intended target cluster, call `GET /api/ecs/clusters/{cluster}/services/` and verify service ARNs, task definition, and desired/running/pending counts against the ECS console or AWS CLI.
3. Call `GET /api/ecs/clusters/{cluster}/tasks/` and verify only live `RUNNING` tasks appear, then inspect one task detail. Confirm task/container ARNs, image digests, start time, CPU/memory, AZ, ENI/private IP, subnet, security groups, and network mode match ECS.
4. Confirm responses contain no environment values, secrets, or credentials.
5. Configure real CloudWatch/Loki endpoints and validate those providers separately. CloudWatch's current resource metrics are configured-service aggregates and must not be interpreted as per-task measurements.
6. Only after discovery validation, enable diagnostic worker execution and check/stop a deliberately approved test task.

If discovery configuration is missing or AWS rejects the task role, the API must return a safe error and no synthetic inventory. No live AWS calls are performed by the repository test suite.

## Deployment sequence

1. build the image
2. tag with an immutable revision
3. push to ECR
4. register or update the ECS task definition
5. update the ECS service
6. wait for deployment stabilization
7. validate health endpoints and browser routes
8. validate unauthenticated API access, diagnostics, and provider access
9. record the deployed revision

## Rollback

Rollback must restore the last known-good ECS task definition and image revision. Keep the previous revision available until the new deployment is healthy.

Record:

- current revision
- previous revision
- image URI
- deployment timestamp
- task definition ARN

## Operational limitations to document

The application currently keeps the following in memory:

- diagnostic session state
- rate-limit windows
- cooldown state
- cleanup-pending state

This means a multi-task ECS deployment does not share state among tasks and should be treated as a configuration risk until the application gains shared storage or a dedicated distributed coordination mechanism.

## Security review checklist

Before production sign-off, verify:

- no credentials in Dockerfile, frontend bundle, or source code
- no wildcard CORS or debug mode
- no public admin ports
- no broad IAM or EC2/RDS/ElastiCache mutation permissions
- correct secret injection path for `DJANGO_SECRET_KEY`
- working CloudWatch Logs stream configuration
- valid HTTPS ingress and same-origin frontend API path
- service remains healthy after deployment

If any required infrastructure or permission cannot be configured safely, stop and document the blocker instead of weakening the security boundary.

## Task 30 validation record

Validation performed on 2026-10-25 from the local Windows development environment. No AWS resources were changed and no live deployment was attempted.

| Area | Status | Evidence |
|---|---|---|
| Backend tests | PASS | Full Django suite passed: 137 tests. The focused production static/SPA routing tests also passed. |
| Django configuration | PASS | `python manage.py check` reported no issues. |
| Python dependencies | PASS | `pip check` reported no broken installed requirements. Production image will install the newly pinned Gunicorn and WhiteNoise dependencies from `backend/requirements.txt`. |
| Frontend typecheck/build | PASS | `npm run typecheck` and `npm run build` succeeded. |
| Production-mode route smoke test | PASS | Local Django with `DJANGO_DEBUG=false` served `/`, `/ecs-resources`, `/api/health/`, and the built `/assets/*` bundle. `/api/ecs/clusters/` safely returned 503 because no AWS discovery configuration is present. |
| Docker build/container | BLOCKED | Docker CLI is installed, but the Docker Desktop Linux engine named pipe is unavailable, so the image could not be built or run. Gunicorn cannot run natively on this Windows host (`fcntl` is unavailable); validate its runtime in the Linux image. |
| AWS identity | BLOCKED | AWS CLI is installed, but STS identity lookup failed; no AWS profile/credentials, `AWS_REGION`, or `DCC_ECS_CLUSTERS` are configured in this environment. |
| ECR | BLOCKED | No AWS identity is available to inspect repository access or push an image. |
| ECS deployment | BLOCKED | No AWS identity or approved target environment is available; no cluster, service, networking, or IAM changes were attempted. |
| Deployed DCC health | BLOCKED | No DCC ECS task was deployed. Local `/api/health/` returned 200. |
| ECS Resources UI route | PASS | The `/ecs-resources` SPA route resolves locally; live inventory is unavailable without AWS discovery configuration. |
| Real ECS discovery | BLOCKED | No AWS identity or configured cluster is available. No live inventory was claimed or fabricated. |
| Diagnostic execution | NOT TESTED | No explicitly approved non-production target was available; no diagnostic was started. |
| CloudWatch | BLOCKED | AWS permissions and a target environment are unavailable. |
| Prometheus | BLOCKED | No configured endpoint is available for a reachability check. |
| Loki | BLOCKED | No configured endpoint or credentials are available for a reachability check. |
| RDS/ElastiCache | BLOCKED | No real dependency resources or AWS permissions are configured for observation. |
| Impact measurement | NOT TESTED | No safe diagnostic session was executed, so there are no baseline/during/post observations to validate. |
| Frontend credential scan | PASS | The built frontend bundle had no matches for AWS access-key patterns, AWS credential variable names, Django secret key, or Loki bearer-token setting. This does not replace image-layer inspection, which was blocked with Docker. |
| Application authentication | PASS | No active DCC login/auth implementation was found; the `/api/auth/login/` 404 assertion is a regression test. |
| Production runtime/static routing | PASS | Replaced Django `runserver` with one Gunicorn worker/four threads and added WhiteNoise compressed manifest storage. Focused routing tests, `collectstatic`, and the local production-mode route smoke test passed. Docker image validation remains blocked. |
| Production security/IAM/HTTPS ingress | BLOCKED | Source configuration requires HTTPS CORS origins and trusts the forwarded HTTPS header, but actual HTTPS ingress, task roles, IAM policies, and image layers could not be inspected without AWS access and Docker. |

The task-definition template parses as JSON and declares one Fargate container with `awsvpc`, port 8000, a health check, CloudWatch Logs configuration, and a Secrets Manager reference for `DJANGO_SECRET_KEY`. Its account, region, image, and environment values are placeholders, not verified deployment values. Runtime IAM and infrastructure configuration remain unverified.

Do not deploy this revision until the full post-change backend suite, a Docker build and local container smoke test succeed, and an authorized AWS identity and approved target environment are available.

## DCC image validation and ECR publication — Task 47

**Validation date:** 2026-10-26  
**Result:** **BLOCKED before ECR push.** DCC tests and the local image validation passed, but the only repository found in `eu-north-1` is the Test Lab repository `dcc-testlab-app`; no existing DCC ECR repository is configured or present. The Test Lab repository was not used for DCC, and no repository or AWS infrastructure was created or modified.

| Check | Status | Result |
|---|---|---|
| Backend regression suite | PASS | `python manage.py test --noinput`: 137 tests passed; Django system check reported no issues. |
| Frontend typecheck | PASS | `npm run typecheck` succeeded. |
| Frontend production build | PASS | `npm run build` succeeded; 2,039 modules transformed. |
| Root Docker build | PASS | Existing root `Dockerfile`, `linux/amd64`; local tag `dcc-app:local-20261026-005213`. |
| Image metadata | PASS | Local image ID `sha256:e4b94cd624c63fc130973420a7671de10adbd57be05501d9b6328ae1b845719f`; size 74,224,604 bytes; port 8000; existing Gunicorn entrypoint. No non-root `USER` is set, so the image defaults to root (**WARN**). |
| Local container | PASS | Bound only to `127.0.0.1:18080`; remained running and Docker health status became `healthy`. `GET /api/health/` returned 200 with `{"status":"ok","service":"dcc-backend"}`. |
| Frontend/static serving | PASS | `GET /` returned 200 and the DCC SPA; its hashed JavaScript and CSS assets returned 200 (471,279 and 108,553 bytes). |
| Image filesystem scan | PASS | Scanned 161 files under application/runtime home paths. No `.env` files, Terraform state/plans, private keys, AWS key patterns, credential URLs, or credential assignments were found. |
| ECR repository discovery | BLOCKED | Read-only `eu-north-1` enumeration returned only `dcc-testlab-app`. This is not a DCC repository and was intentionally left unchanged. |
| Immutable ECR tag/digest | NOT RUN | No DCC image was pushed; therefore no ECR tag or registry digest exists for this task. |
| Pull-back verification | NOT RUN | Requires a DCC repository image/tag, which is blocked by the missing repository. |
| ECS/Terraform | NOT RUN | No ECS deployment, Terraform plan/apply, or Terraform state change was performed. |

Two packaging issues were fixed before the final local validation: `docker-entrypoint.sh` had CRLF line endings that caused `set -eu` to fail in the Linux image, so its line endings were normalized; the image scan also found the placeholder `backend/.env.example`, so `.dockerignore` now excludes nested `.env` and `.env.*` files. The final image was rebuilt and passed the runtime and filesystem checks. No Dockerfile or application source changes were made.

**WARN:** The local `/api/services/` live-discovery route safely returned HTTP 503 without AWS discovery configuration/credentials; the local backend health route and full container health check passed.  
**Follow-up:** Tasks 48A and 48B below provisioned the dedicated DCC repository and published/pull-verified an immutable image. Any ECS deployment remains separately authorized; do not use `dcc-testlab-app` for DCC.

## Task 48B — DCC image publication

**Date:** 2026-10-26  
**Status:** **PASS** (ECR scan findings pending)

- Regression checks passed: backend **137 tests**, frontend typecheck, and frontend production build.
- Built the root `Dockerfile` for `linux/amd64`, tag `dcc-20261026-010107`.
- Published `366314473733.dkr.ecr.eu-north-1.amazonaws.com/dcc-app:dcc-20261026-010107`.
- Registry digest: `sha256:57ad794443ebb36b0b3409b2491aa985bd96d5b20da0fb96b6e5762e5a49510c`; ECR image size: 74,221,176 bytes.
- Local smoke and registry pull-back passed: API health, SPA shell, and JS/CSS assets returned 200; pulled image digest matched ECR and Docker health became healthy.
- Credential/content scan passed: no credentials, real private keys, environment files, or Terraform state/plans were found.
- ECR scan-on-push is enabled; AWS had not yet made scan findings available when checked.
- Temporary containers and local pushed-image tag were removed. No ECS deployment or Terraform operation was performed.

This image is ready for a separately authorized deployment task; this record does not claim ECS deployment.

## Task 49A — Non-root DCC image

**Date:** 2026-10-26  
**Status:** **PASS**

The earlier Task 47/48B note that the DCC image defaulted to root is superseded. The root `Dockerfile` now creates a dedicated `dcc` user and runs the final image as `USER 10001:10001`; its home and Gunicorn control-socket directory are writable while application files remain root-owned/read-only.

- Backend: **137 tests passed**. Frontend typecheck and production build: **PASS**.
- Built `linux/amd64` and published immutable tag `dcc-20261026-021508` to `366314473733.dkr.ecr.eu-north-1.amazonaws.com/dcc-app`.
- Verified ECR digest: `sha256:cc2403f273f1ef120a668d7bf7c2b96743ffba4e27f00a588f5627a9047621e0`.
- Local and pull-back checks confirmed image user and Gunicorn UID/GID `10001`, healthy startup, and HTTP 200 for `/api/health/`, `/`, and JS/CSS assets. The content scan found no credentials, actual private keys, environment files, or Terraform state/plans.
- Temporary containers/local image were removed. The earlier ECR image was not deleted. No Terraform or ECS resources were changed.

Use the digest above for a separately authorized ECS task; do not override the container user.

## Task 49B — DCC ECS deployment attempt

**Date:** 2026-10-26  
**Status:** **BLOCKED — partial Terraform apply**

The reviewed DCC deployment plan applied the DCC task definition, CloudWatch log group, private Cloud Map A-record service, generated Django secret, diagnostic-only SG rules, and the DCC additions to the existing ECS execution policy. ECS service creation failed because Terraform specified a `container_port` for an A-record Cloud Map registry, which ECS rejects. No DCC ECS service/task is running. The existing Test Lab API and Worker remain 1/1; RDS and Redis remain available.

The partial resources remain tracked in local Terraform state; preserve that state. A fresh plan and further apply were not run. Resolve the A-record service registry configuration and review a new plan before continuing.

## Task 49D — DCC private ECS deployment

**Date:** 2026-10-26  
**Status:** **PASS**

The Cloud Map registry configuration was corrected to reference the existing A-record service without `container_name` or `container_port`. A fresh plan contained only the DCC ECS service creation (`1 add, 0 change, 0 destroy`) and was applied with Terraform.

- Cluster/service: `dcc-testlab-cluster` / `dcc-app-service`; desired/running/pending counts are `1/1/0`.
- Task: `f2880f5700354fe889b9dbad22342043`, definition `dcc-app:1`, running image `366314473733.dkr.ecr.eu-north-1.amazonaws.com/dcc-app@sha256:cc2403f273f1ef120a668d7bf7c2b96743ffba4e27f00a588f5627a9047621e0`, container user `10001:10001`.
- The service uses the existing private application subnet and DCC control security group, has no public IP, and is registered with the existing `dcc-app` A-record service in `dcc-test.internal`.
- Private smoke checks returned `/api/health/` **200**, `/` **200**, and a JS asset **200**. `/api/services/` returned **503**, an allowed outcome when AWS discovery is not configured. CloudWatch startup logs were normal. Test Lab API and Worker remained `1/1`.
- **Caveat:** Cloud Map discovery returns the DCC task and private address, but its `AWS_INIT_HEALTH_STATUS` attribute is `UNHEALTHY`; ECS reports the task/container healthy and private HTTP checks succeeded. Do not represent this Cloud Map health attribute as healthy.
- Final Terraform plan: **No changes**. No secrets were exposed; no unrelated infrastructure was changed.
