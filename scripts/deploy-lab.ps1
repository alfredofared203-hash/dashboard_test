[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Region = "eu-north-1"
$ExpectedAccount = "366314473733"
$Cluster = "dcc-testlab-cluster"
$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$TerraformDirectory = Join-Path $RepositoryRoot "infra\terraform\test-lab"
$BackendDirectory = Join-Path $RepositoryRoot "backend"
$FrontendDirectory = Join-Path $RepositoryRoot "frontend"
$TestAppDirectory = Join-Path $RepositoryRoot "test-app"
$TemporaryDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ("dcc-lab-deploy-" + [guid]::NewGuid().ToString("N"))
$PlanPath = Join-Path $TemporaryDirectory "reviewed.tfplan"
$ProbeInputPath = Join-Path $TemporaryDirectory "private-smoke.json"
$TestTag = "test-" + (Get-Date -Format "yyyyMMdd-HHmmss")
$DccTag = "dcc-" + (Get-Date -Format "yyyyMMdd-HHmmss")
$Registry = "$ExpectedAccount.dkr.ecr.$Region.amazonaws.com"
$TestImage = "$Registry/dcc-testlab-app`:$TestTag"
$DccImage = "$Registry/dcc-app`:$DccTag"
$SmokeTaskArn = $null

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)][string]$Executable,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Executable failed with exit code $LASTEXITCODE."
    }
}

function Get-NativeText {
    param(
        [Parameter(Mandatory = $true)][string]$Executable,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    $result = & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Executable failed with exit code $LASTEXITCODE."
    }
    return ($result -join [Environment]::NewLine).Trim()
}

function Get-ImageDigest {
    param(
        [Parameter(Mandatory = $true)][string]$Repository,
        [Parameter(Mandatory = $true)][string]$Tag
    )

    $digest = Get-NativeText "aws" @(
        "ecr", "describe-images", "--region", $Region,
        "--repository-name", $Repository, "--image-ids", "imageTag=$Tag",
        "--query", "imageDetails[0].imageDigest", "--output", "text"
    )
    if ($digest -notmatch "^sha256:[0-9a-f]{64}$") {
        throw "ECR did not return a valid immutable digest for $Repository`:$Tag."
    }
    return $digest
}

function Assert-ImageContainsNoSecretsOrState {
    param([Parameter(Mandatory = $true)][string]$Image)

    $scan = "import pathlib,re,sys; roots=[pathlib.Path('/app'),pathlib.Path('/home/dcc')]; forbidden=re.compile(r'\.env(\..*)?|.*\.tfstate(\..*)?|.*\.(tfplan|plan|pem|key)|id_(rsa|ed25519)',re.I); marker=re.compile(rb'-----BEGIN [A-Z ]*PRIVATE KEY-----|AKIA[0-9A-Z]{16}'); bad=[]; files=(p for root in roots if root.exists() for p in root.rglob('*') if p.is_file()); [(bad.append(str(p)) if forbidden.fullmatch(p.name) or marker.search(p.read_bytes()) else None) for p in files]; print('IMAGE_CONTENT_SCAN=FAIL files='+','.join(bad) if bad else 'IMAGE_CONTENT_SCAN=PASS'); sys.exit(bool(bad))"
    Invoke-Native "docker" @("run", "--rm", "--entrypoint", "python", $Image, "-c", $scan)
}

function Get-TaskForService {
    param([Parameter(Mandatory = $true)][string]$ServiceName)

    $taskArn = Get-NativeText "aws" @(
        "ecs", "list-tasks", "--region", $Region, "--cluster", $Cluster,
        "--service-name", $ServiceName, "--desired-status", "RUNNING",
        "--query", "taskArns[0]", "--output", "text"
    )
    if (-not $taskArn -or $taskArn -eq "None") {
        throw "No running task was found for ECS service $ServiceName."
    }
    $json = Get-NativeText "aws" @(
        "ecs", "describe-tasks", "--region", $Region, "--cluster", $Cluster,
        "--tasks", $taskArn, "--output", "json"
    )
    return (($json | ConvertFrom-Json).tasks[0])
}

function Assert-CurrentTaskLogs {
    param(
        [Parameter(Mandatory = $true)][string]$LogGroup,
        [Parameter(Mandatory = $true)][string]$StreamPrefix,
        [Parameter(Mandatory = $true)][string]$ContainerName,
        [Parameter(Mandatory = $true)][string]$TaskId
    )

    $stream = "$StreamPrefix/$ContainerName/$TaskId"
    $json = Get-NativeText "aws" @(
        "logs", "get-log-events", "--region", $Region,
        "--log-group-name", $LogGroup, "--log-stream-name", $stream,
        "--start-from-head", "--limit", "200", "--output", "json"
    )
    $events = ($json | ConvertFrom-Json).events
    if ($events.Count -eq 0) {
        throw "No startup logs were found for $ContainerName task $TaskId."
    }
    $failurePattern = "Traceback|Permission denied|AccessDenied|Gunicorn.*(fail|error)|database.*(fail|error)|Redis.*(fail|error)|secret.*(fail|missing)|configuration.*(fail|missing)"
    foreach ($event in $events) {
        if ($event.message -match $failurePattern) {
            throw "A startup, permission, database, Redis, or configuration error was found in $ContainerName logs. Inspect the task's CloudWatch stream."
        }
    }
    Write-Host "PASS: current $ContainerName task logs contain no matched startup/dependency errors."
}

function Assert-ServiceTask {
    param(
        [Parameter(Mandatory = $true)][object]$Service,
        [Parameter(Mandatory = $true)][string]$ExpectedImage,
        [Parameter(Mandatory = $true)][string]$ExpectedSecurityGroup
    )

    if ($Service.desiredCount -ne 1 -or $Service.runningCount -ne 1 -or $Service.pendingCount -ne 0) {
        throw "ECS service $($Service.serviceName) is not stable at 1/1/0."
    }
    if ($Service.deployments.Count -ne 1 -or $Service.deployments[0].rolloutState -ne "COMPLETED") {
        throw "ECS service $($Service.serviceName) does not have one completed deployment."
    }
    $configuration = $Service.networkConfiguration.awsvpcConfiguration
    if ($configuration.assignPublicIp -ne "DISABLED" -or $ExpectedSecurityGroup -notin $configuration.securityGroups) {
        throw "ECS service $($Service.serviceName) has an unexpected public-IP or security-group configuration."
    }
    foreach ($subnet in $configuration.subnets) {
        if ($subnet -notin $PrivateSubnets) {
            throw "ECS service $($Service.serviceName) uses a subnet outside the private application tier."
        }
    }

    $task = Get-TaskForService $Service.serviceName
    if ($task.lastStatus -ne "RUNNING" -or $task.containers[0].imageDigest -ne $ExpectedImage.Split("@")[-1]) {
        throw "The running task for $($Service.serviceName) is not running the expected image digest."
    }
    if ($Service.serviceName -eq "dcc-app-service" -and $task.containers[0].healthStatus -ne "HEALTHY") {
        throw "The DCC container did not report HEALTHY."
    }
    foreach ($detail in $task.attachments[0].details) {
        if ($detail.name -eq "subnetId" -and $detail.value -notin $PrivateSubnets) {
            throw "The running task for $($Service.serviceName) is outside the private application subnets."
        }
    }
    $eni = ($task.attachments[0].details | Where-Object { $_.name -eq "networkInterfaceId" }).value
    if (-not $eni) {
        throw "The running task for $($Service.serviceName) has no discoverable network interface."
    }
    $publicIp = Get-NativeText "aws" @(
        "ec2", "describe-network-interfaces", "--region", $Region,
        "--network-interface-ids", $eni,
        "--query", "NetworkInterfaces[0].Association.PublicIp", "--output", "text"
    )
    if ($publicIp -and $publicIp -ne "None") {
        throw "The running task for $($Service.serviceName) has a public IP."
    }

    $taskDefinitionJson = Get-NativeText "aws" @(
        "ecs", "describe-task-definition", "--region", $Region,
        "--task-definition", $Service.taskDefinition, "--output", "json"
    )
    $definition = ($taskDefinitionJson | ConvertFrom-Json).taskDefinition
    if ($definition.containerDefinitions[0].image -ne $ExpectedImage) {
        throw "Task definition $($Service.taskDefinition) does not pin the expected image digest."
    }
    if ($Service.serviceName -eq "dcc-app-service" -and $definition.containerDefinitions[0].user -ne "10001:10001") {
        throw "DCC task definition does not specify user 10001:10001."
    }
    if ($Service.serviceName -eq "dcc-app-service") {
        $container = $definition.containerDefinitions[0]
        if ($container.logConfiguration.options."awslogs-group" -ne "/ecs/dcc-testlab/dcc-app") {
            throw "DCC task definition does not use the existing DCC CloudWatch log group."
        }
        $secretReference = $container.secrets | Where-Object { $_.name -eq "DJANGO_SECRET_KEY" }
        if (-not $secretReference -or $secretReference.valueFrom -notmatch "dcc-app-django-secret-key") {
            throw "DCC task definition does not reference the existing Django secret through Secrets Manager."
        }
    }
    return $task
}

function Invoke-PrivateSmokeTest {
    param(
        [Parameter(Mandatory = $true)][string]$ApiTaskDefinition,
        [Parameter(Mandatory = $true)][string[]]$Subnets,
        [Parameter(Mandatory = $true)][string]$DiagnosticSecurityGroup
    )

    $probe = @'
import http.client
import json
import os
import uuid
from html.parser import HTMLParser
from redis import Redis

class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []
    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        for key in ("src", "href"):
            value = values.get(key)
            if value and value.split("?", 1)[0].endswith((".js", ".css")):
                self.paths.append(value.split("?", 1)[0])

def request(host, port, path, method="GET", body=None):
    conn = http.client.HTTPConnection(host, port, timeout=45)
    try:
        data = None if body is None else json.dumps(body).encode()
        headers = {} if data is None else {"Content-Type": "application/json"}
        conn.request(method, path, body=data, headers=headers)
        response = conn.getresponse()
        content = response.read()
        print(f"CHECK {method} {path} HTTP {response.status}", flush=True)
        if response.status != 200:
            raise RuntimeError(f"{method} {path} returned HTTP {response.status}")
        return content
    finally:
        conn.close()

dcc = "dcc-app.dcc-test.internal"
api = "dcc-test-api.dcc-test.internal"
request(dcc, 8000, "/api/health/")
root = request(dcc, 8000, "/")
parser = Assets()
parser.feed(root.decode("utf-8", "replace"))
if not parser.paths:
    raise RuntimeError("No JS/CSS asset was discoverable from the DCC root page")
request(dcc, 8000, parser.paths[0])
services = json.loads(request(dcc, 8000, "/api/services/"))
print(f"CHECK GET /api/services/ discovered={len(services)}", flush=True)
for path in ("/health", "/ready", "/metrics", "/api/products", "/api/orders"):
    response = request(api, 8080, path)
    if path == "/ready":
        dependencies = json.loads(response).get("dependencies", {})
        if dependencies.get("postgresql", {}).get("status") != "available":
            raise RuntimeError("PostgreSQL readiness failed")
        if dependencies.get("redis", {}).get("status") != "available":
            raise RuntimeError("Redis readiness failed")

client = Redis.from_url(os.environ["REDIS_URL"])
key = "test-laboratory:deploy-probe:" + uuid.uuid4().hex
value = uuid.uuid4().hex
try:
    if not client.set(key, value, ex=60) or client.get(key).decode() != value:
        raise RuntimeError("Redis temporary-key readback failed")
    print("CHECK Redis temporary-key write/readback PASS", flush=True)
finally:
    client.delete(key)
    client.close()
print("PRIVATE_SMOKE=PASS", flush=True)
'@
    $request = @{
        cluster = $Cluster
        taskDefinition = $ApiTaskDefinition
        count = 1
        launchType = "FARGATE"
        networkConfiguration = @{
            awsvpcConfiguration = @{
                subnets = $Subnets
                securityGroups = @($DiagnosticSecurityGroup)
                assignPublicIp = "DISABLED"
            }
        }
        overrides = @{
            containerOverrides = @(@{
                name = "api"
                command = @("python", "-c", $probe)
            })
        }
    }
    $request | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $ProbeInputPath -Encoding Ascii
    $runJson = Get-NativeText "aws" @(
        "ecs", "run-task", "--region", $Region, "--cli-input-json", "file://$ProbeInputPath",
        "--output", "json"
    )
    $run = $runJson | ConvertFrom-Json
    if ($run.failures.Count -gt 0 -or $run.tasks.Count -ne 1) {
        throw "The private smoke-test task could not be started."
    }
    $script:SmokeTaskArn = $run.tasks[0].taskArn
    Invoke-Native "aws" @(
        "ecs", "wait", "tasks-stopped", "--region", $Region,
        "--cluster", $Cluster, "--tasks", $script:SmokeTaskArn,
        "--delay", "10", "--max-attempts", "60"
    )
    $taskJson = Get-NativeText "aws" @(
        "ecs", "describe-tasks", "--region", $Region, "--cluster", $Cluster,
        "--tasks", $script:SmokeTaskArn, "--output", "json"
    )
    $task = ($taskJson | ConvertFrom-Json).tasks[0]
    $script:SmokeTaskArn = $null
    if ($task.containers[0].exitCode -ne 0) {
        throw "The private smoke-test task failed. Inspect its API CloudWatch task stream."
    }
    Write-Host "PASS: private DCC, Test API, PostgreSQL, and Redis smoke checks."
}

New-Item -ItemType Directory -Path $TemporaryDirectory | Out-Null
try {
    foreach ($command in @("aws", "terraform", "docker", "npm")) {
        if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
            throw "Required command '$command' was not found in PATH."
        }
    }
    $identity = Get-NativeText "aws" @("sts", "get-caller-identity", "--query", "Account", "--output", "text")
    if ($identity -ne $ExpectedAccount) {
        throw "AWS identity account $identity does not match expected lab account $ExpectedAccount."
    }
    Write-Host "PASS: AWS identity is account $ExpectedAccount; region $Region."

    Push-Location $TerraformDirectory
    try {
        Invoke-Native "terraform" @("init", "-input=false")
        Invoke-Native "terraform" @("fmt", "-check", "-recursive")
        Invoke-Native "terraform" @("validate", "-no-color")
        $state = Get-NativeText "terraform" @("state", "list")
        if ($state -notmatch "aws_vpc\.test_lab" -or $state -notmatch "aws_ecs_service\.dcc_app") {
            throw "The existing Terraform state is missing expected lab resources; refusing to initialize a new deployment."
        }
        Write-Host "PASS: existing Terraform state and configuration are available."
    }
    finally {
        Pop-Location
    }

    $backendPython = Join-Path $BackendDirectory ".venv\Scripts\python.exe"
    if (-not (Test-Path $backendPython)) { $backendPython = (Get-Command python -ErrorAction Stop).Source }
    Push-Location $BackendDirectory
    try { Invoke-Native $backendPython @("manage.py", "test") }
    finally { Pop-Location }

    Push-Location $FrontendDirectory
    try {
        Invoke-Native "npm" @("run", "typecheck")
        Invoke-Native "npm" @("run", "build")
    }
    finally { Pop-Location }

    $testPython = Join-Path $TestAppDirectory ".venv\Scripts\python.exe"
    if (-not (Test-Path $testPython)) { $testPython = (Get-Command python -ErrorAction Stop).Source }
    Push-Location $TestAppDirectory
    try { Invoke-Native $testPython @("-m", "pytest") }
    finally { Pop-Location }

    $testAppDockerfile = Join-Path $TestAppDirectory "Dockerfile"
    Invoke-Native "docker" @(
        "buildx", "build", "--platform", "linux/amd64", "--load",
        "-f", $testAppDockerfile, "-t", $TestImage, $TestAppDirectory
    )
    Invoke-Native "docker" @("buildx", "build", "--platform", "linux/amd64", "--load", "-t", $DccImage, $RepositoryRoot)
    foreach ($image in @($TestImage, $DccImage)) {
        $imageFacts = Get-NativeText "docker" @(
            "image", "inspect", "--format", "{{.Os}}/{{.Architecture}}|{{.Config.User}}", $image
        )
        if ($imageFacts -ne "linux/amd64|10001:10001") {
            throw "Image $image has unexpected architecture or non-root user '$imageFacts'."
        }
        Write-Host "PASS: $image is linux/amd64 and runs as UID/GID 10001:10001."
        Assert-ImageContainsNoSecretsOrState $image
    }

    $loginPassword = Get-NativeText "aws" @("ecr", "get-login-password", "--region", $Region)
    $loginPassword | & docker login --username AWS --password-stdin $Registry
    $loginExitCode = $LASTEXITCODE
    $loginPassword = $null
    if ($loginExitCode -ne 0) { throw "Docker login to the lab ECR registry failed." }
    Invoke-Native "docker" @("push", $TestImage)
    Invoke-Native "docker" @("push", $DccImage)
    $TestDigest = Get-ImageDigest "dcc-testlab-app" $TestTag
    $DccDigest = Get-ImageDigest "dcc-app" $DccTag
    Write-Host "Test Lab image digest: $TestDigest"
    Write-Host "DCC image digest: $DccDigest"

    $secretValue = Get-NativeText "aws" @(
        "secretsmanager", "get-secret-value", "--region", $Region,
        "--secret-id", "dcc-app-django-secret-key", "--query", "SecretString", "--output", "text"
    )
    if ($secretValue.Length -lt 50) {
        throw "The existing DCC signing secret is missing or invalid; no replacement will be generated."
    }
    $env:TF_VAR_dcc_django_secret = $secretValue
    $secretValue = $null
    $env:TF_VAR_test_app_image_digest = $TestDigest
    $env:TF_VAR_dcc_app_image_digest = $DccDigest

    Push-Location $TerraformDirectory
    try {
        Invoke-Native "terraform" @("plan", "-input=false", "-no-color", "-out=$PlanPath")
        $planJson = Get-NativeText "terraform" @("show", "-json", $PlanPath)
        $plan = $planJson | ConvertFrom-Json
        $allowedTaskDefinitions = @(
            "aws_ecs_task_definition.dcc_app",
            "aws_ecs_task_definition.test_api",
            "aws_ecs_task_definition.test_worker"
        )
        $allowedServices = @(
            "aws_ecs_service.dcc_app",
            "aws_ecs_service.test_api",
            "aws_ecs_service.test_worker"
        )
        foreach ($change in $plan.resource_changes) {
            $actions = @($change.change.actions)
            if ($actions.Count -eq 1 -and $actions[0] -eq "no-op") { continue }
            $address = $change.address
            $actionText = $actions -join ","
            if ($change.mode -eq "data" -and $actions.Count -eq 1 -and $actions[0] -eq "read") {
                Write-Host "Planned data-source refresh: $address"
                continue
            }
            Write-Host "Planned managed-resource action: $address [$actionText]"
            if ($change.mode -ne "managed") {
                throw "Unexpected non-managed Terraform plan action at $address."
            }
            if ($address -in $allowedTaskDefinitions -and (
                ($actions.Count -eq 1 -and $actions[0] -eq "create") -or
                ($actions.Count -eq 2 -and $actions[0] -eq "create" -and $actions[1] -eq "delete") -or
                ($actions.Count -eq 2 -and $actions[0] -eq "delete" -and $actions[1] -eq "create")
            )) { continue }
            if ($address -in $allowedServices -and $actions.Count -eq 1 -and $actions[0] -eq "update") { continue }
            if ($address -eq "aws_iam_role_policy.dcc_ecs_discovery" -and $actions.Count -eq 1 -and $actions[0] -eq "update") { continue }
            throw "Terraform plan contains an unapproved action at $address [$actionText]; no apply was performed."
        }
        Write-Host "Plan review passed: only image-driven task-definition revisions, ECS service updates, and an in-place DCC discovery policy update are allowed."
        $approval = Read-Host "Apply this exact saved plan to the existing lab? Type APPLY to continue"
        if ($approval -cne "APPLY") {
            throw "Apply cancelled; the saved plan was not applied."
        }
        Invoke-Native "terraform" @("apply", "-input=false", $PlanPath)
    }
    finally {
        Pop-Location
    }

    Invoke-Native "aws" @(
        "ecs", "wait", "services-stable", "--region", $Region, "--cluster", $Cluster,
        "--services", "dcc-app-service", "api-service", "worker-service"
    )
    $subnetsJson = Get-NativeText "terraform" @("-chdir=$TerraformDirectory", "output", "-json", "private_application_subnet_ids")
    $PrivateSubnets = @($subnetsJson | ConvertFrom-Json)
    $securityGroupsJson = Get-NativeText "terraform" @("-chdir=$TerraformDirectory", "output", "-json", "security_group_ids")
    $securityGroups = $securityGroupsJson | ConvertFrom-Json
    $servicesJson = Get-NativeText "aws" @(
        "ecs", "describe-services", "--region", $Region, "--cluster", $Cluster,
        "--services", "dcc-app-service", "api-service", "worker-service", "--output", "json"
    )
    $services = ($servicesJson | ConvertFrom-Json).services
    $taskImages = @{
        "dcc-app-service" = "$Registry/dcc-app@$DccDigest"
        "api-service" = "$Registry/dcc-testlab-app@$TestDigest"
        "worker-service" = "$Registry/dcc-testlab-app@$TestDigest"
    }
    $taskSecurityGroups = @{
        "dcc-app-service" = $securityGroups.dcc_control
        "api-service" = $securityGroups.test_api
        "worker-service" = $securityGroups.test_worker
    }
    $runningTasks = @{}
    foreach ($service in $services) {
        $runningTasks[$service.serviceName] = Assert-ServiceTask $service $taskImages[$service.serviceName] $taskSecurityGroups[$service.serviceName]
        Write-Host "PASS: $($service.serviceName) desired/running/pending=1/1/0; pinned image and private networking verified."
    }

    $rdsJson = Get-NativeText "aws" @(
        "rds", "describe-db-instances", "--region", $Region, "--db-instance-identifier", "dcc-testlab-postgres", "--output", "json"
    )
    $rds = ($rdsJson | ConvertFrom-Json).DBInstances[0]
    if ($rds.DBInstanceStatus -ne "available" -or $rds.PubliclyAccessible -or -not $rds.StorageEncrypted) {
        throw "PostgreSQL is not available, private, and encrypted."
    }
    $redisJson = Get-NativeText "aws" @(
        "elasticache", "describe-replication-groups", "--region", $Region,
        "--replication-group-id", "dcc-testlab-redis", "--output", "json"
    )
    $redis = ($redisJson | ConvertFrom-Json).ReplicationGroups[0]
    if ($redis.Status -ne "available" -or -not $redis.AtRestEncryptionEnabled -or -not $redis.TransitEncryptionEnabled) {
        throw "Redis is not available with at-rest and in-transit encryption."
    }

    foreach ($cloudMapService in @("dcc-app", "dcc-test-api")) {
        $instances = Get-NativeText "aws" @(
            "servicediscovery", "discover-instances", "--region", $Region,
            "--namespace-name", "dcc-test.internal", "--service-name", $cloudMapService,
            "--query", "Instances[].InstanceId", "--output", "text"
        )
        if (-not $instances -or $instances -eq "None") {
            throw "Cloud Map service $cloudMapService has no registered instance."
        }
        Write-Host "PASS: Cloud Map $cloudMapService has a registered task instance."
    }

    $apiTaskDefinition = ($services | Where-Object { $_.serviceName -eq "api-service" }).taskDefinition
    Invoke-PrivateSmokeTest $apiTaskDefinition $PrivateSubnets $securityGroups.diagnostic_worker

    Assert-CurrentTaskLogs "/ecs/dcc-testlab/dcc-app" "dcc" "dcc-app" $runningTasks["dcc-app-service"].taskArn.Split("/")[-1]
    Assert-CurrentTaskLogs "/ecs/dcc-testlab/api" "api" "api" $runningTasks["api-service"].taskArn.Split("/")[-1]
    Assert-CurrentTaskLogs "/ecs/dcc-testlab/worker" "worker" "worker" $runningTasks["worker-service"].taskArn.Split("/")[-1]

    Push-Location $TerraformDirectory
    try {
        $finalPlan = Get-NativeText "terraform" @("plan", "-input=false", "-no-color")
        Write-Host $finalPlan
        if ($finalPlan -notmatch "No changes") {
            throw "Final Terraform plan is not clean."
        }
    }
    finally {
        Pop-Location
    }
    Write-Host "PASS: deployment complete; all services, dependencies, private smoke checks, logs, and final Terraform plan verified."
}
catch {
    Write-Error ("FAIL: " + $_.Exception.Message)
    throw
}
finally {
    if ($SmokeTaskArn) {
        & aws ecs stop-task --region $Region --cluster $Cluster --task $SmokeTaskArn --reason "Deployment smoke test cleanup" | Out-Null
    }
    Remove-Item Env:\TF_VAR_dcc_django_secret -ErrorAction SilentlyContinue
    Remove-Item Env:\TF_VAR_test_app_image_digest -ErrorAction SilentlyContinue
    Remove-Item Env:\TF_VAR_dcc_app_image_digest -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $TemporaryDirectory) {
        Remove-Item -LiteralPath $TemporaryDirectory -Recurse -Force
    }
}
