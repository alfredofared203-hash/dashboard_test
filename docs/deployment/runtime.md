# DCC Production Runtime

This document defines the runtime contract for the single-image production deployment of the DevOps Control Center (DCC).

## Single-image requirement

The repository produces exactly one Docker image containing both the React frontend and the Django backend. The frontend is compiled in a Node build stage and copied into the Python runtime image. Django serves the compiled SPA at `/` and the API at `/api/*` from the same origin.

## Runtime layout

- `GET /` -> compiled React app
- `GET /api/health/` -> Django health endpoint
- `GET /api/...` -> Django API routes
- `GET /assets/...` -> compiled frontend static files

The app must not require a separate Vite dev server or a second container in production.

The production image runs Django through Gunicorn, with one worker and four threads. Keep one worker while diagnostic state and rate limits are process-local; changing worker count requires shared state across processes. WhiteNoise serves collected frontend assets at `/assets/*` from the same container.

The Dockerfile keeps `DJANGO_DEBUG=false` in the runtime image. It temporarily enables debug settings only for the build-time `collectstatic` command, so static collection does not need a build-time `DJANGO_SECRET_KEY`.

## Required environment variables

The container should be started with production-safe settings such as:

```bash
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=<strong secret>
DJANGO_ALLOWED_HOSTS=app.example.com
DCC_CORS_ALLOWED_ORIGINS=https://app.example.com
AWS_REGION=us-east-1
DCC_ECS_CLUSTERS=existing-workload-cluster
PORT=8000
```

Additional runtime values remain optional and should track the enabled providers only:

```bash
DCC_DIAGNOSTIC_PROVIDER=ecs
DCC_METRICS_PROVIDER=cloudwatch
DCC_LOGS_PROVIDER=loki
DCC_DEPENDENCIES_PROVIDER=cloudwatch
DCC_CLOUDWATCH_REGION=us-east-1
DCC_CLOUDWATCH_CLUSTER_NAME=existing-workload-cluster
DCC_CLOUDWATCH_SERVICE_NAME=existing-workload-service
DCC_CLOUDWATCH_ECS_NAMESPACE=AWS/ECS
DCC_CLOUDWATCH_CONTAINER_INSIGHTS_NAMESPACE=ECS/ContainerInsights
DCC_PROMETHEUS_URL=
DCC_LOKI_URL=https://loki.example.internal
```

`AWS_REGION` and `DCC_ECS_CLUSTERS` are required for real ECS discovery. The cluster list is an explicit allowlist, not an account-wide scan. The `DCC_ECS_CLUSTER`, `DCC_ECS_TASK_DEFINITION`, `DCC_ECS_SUBNETS`, and `DCC_ECS_CONTAINER_NAME` values are additionally required to enable diagnostic worker execution. CloudWatch metrics and Loki logs must be configured with real endpoints/dimensions or the corresponding API surfaces return safe unavailable errors.

## Health and readiness

The application container exposes port `8000` and should answer:

```text
GET /api/health/
```

The Dockerfile uses a lightweight health check against this endpoint. This ensures that the container is considered healthy only when the application is capable of serving a simple unauthenticated status page.

## Security constraints

- Do not set `DJANGO_DEBUG=true` in production.
- Do not expose credentials in environment variables or frontend bundle artifacts.
- Do not use wildcard CORS origins.
- Use HTTPS only for browser ingress.
- Keep the container single-tenant and single-task unless explicitly approved.

## Process-local state limitation

The current DCC architecture stores diagnostic state, rate limits, cooldowns, and cleanup flags in process memory. That means:

- more than one application task does not share diagnostic state
- restart or scale-out invalidates in-memory session state
- production deployment should prefer a single application task

This is an application design limitation, not a deployment workaround.

## Deployment note

The canonical deployment path is:

1. Build the image from the repo root.
2. Tag with an immutable revision.
3. Push to the target ECR repository.
4. Register/update a single ECS task definition.
5. Deploy a single ECS service.
6. Validate the health endpoint and browser routes.

The repository intentionally keeps the development workflow separate from the production runtime contract. Development continues to use Vite on port 5173 with `VITE_API_BASE_URL` when needed; production uses the same origin.
