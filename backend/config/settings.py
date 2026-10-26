import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured


BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ImproperlyConfigured(f"{name} must be a boolean value.")


def env_csv(name: str) -> list[str]:
    return [
        item.strip()
        for item in os.environ.get(name, "").split(",")
        if item.strip()
    ]


def env_int(name: str, default: int, *, minimum: int = 1) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError as error:
        raise ImproperlyConfigured(f"{name} must be an integer.") from error
    if parsed < minimum:
        raise ImproperlyConfigured(f"{name} must be at least {minimum}.")
    return parsed


DEBUG = os.environ.get("DJANGO_DEBUG", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is disabled."
        )
    SECRET_KEY = "development-only-insecure-key-do-not-use-in-production"

_default_allowed_hosts = "localhost,127.0.0.1,[::1]"
_configured_allowed_hosts = env_csv("DJANGO_ALLOWED_HOSTS")
if DEBUG:
    ALLOWED_HOSTS = _configured_allowed_hosts or [
        host.strip()
        for host in _default_allowed_hosts.split(",")
        if host.strip()
    ]
else:
    if not _configured_allowed_hosts:
        raise ImproperlyConfigured(
            "DJANGO_ALLOWED_HOSTS must be set when DJANGO_DEBUG is disabled."
        )
    ALLOWED_HOSTS = _configured_allowed_hosts

AWS_REGION = os.environ.get("AWS_REGION", "").strip()
DCC_ECS_CLUSTERS = env_csv("DCC_ECS_CLUSTERS")
DCC_ECS_CLUSTER = os.environ.get("DCC_ECS_CLUSTER", "").strip()
DCC_ECS_TASK_DEFINITION = os.environ.get("DCC_ECS_TASK_DEFINITION", "").strip()
DCC_ECS_SUBNETS = env_csv("DCC_ECS_SUBNETS")
DCC_ECS_SECURITY_GROUPS = env_csv("DCC_ECS_SECURITY_GROUPS")
DCC_ECS_CONTAINER_NAME = os.environ.get("DCC_ECS_CONTAINER_NAME", "").strip()
DCC_ECS_ASSIGN_PUBLIC_IP = env_bool("DCC_ECS_ASSIGN_PUBLIC_IP", default=False)
DCC_ECS_MAX_TASK_CPU = env_int("DCC_ECS_MAX_TASK_CPU", 1024)
DCC_ECS_MAX_TASK_MEMORY_MIB = env_int("DCC_ECS_MAX_TASK_MEMORY_MIB", 2048)
DCC_DIAGNOSTIC_PROVIDER = os.environ.get(
    "DCC_DIAGNOSTIC_PROVIDER", "inmemory"
).strip().lower()
if DCC_DIAGNOSTIC_PROVIDER not in {"inmemory", "ecs"}:
    raise ImproperlyConfigured(
        "DCC_DIAGNOSTIC_PROVIDER must be either 'inmemory' or 'ecs'."
    )
DCC_DIAGNOSTIC_MAX_DURATION_SECONDS = env_int(
    "DCC_DIAGNOSTIC_MAX_DURATION_SECONDS", 900
)
DCC_DIAGNOSTIC_MAX_ACTIVE_SESSIONS = env_int(
    "DCC_DIAGNOSTIC_MAX_ACTIVE_SESSIONS", 1
)
DCC_DIAGNOSTIC_START_RATE_LIMIT = env_int(
    "DCC_DIAGNOSTIC_START_RATE_LIMIT", 3
)
DCC_DIAGNOSTIC_START_RATE_WINDOW_SECONDS = env_int(
    "DCC_DIAGNOSTIC_START_RATE_WINDOW_SECONDS", 3600
)
DCC_DIAGNOSTIC_STOP_RATE_LIMIT = env_int(
    "DCC_DIAGNOSTIC_STOP_RATE_LIMIT", 10
)
DCC_DIAGNOSTIC_STOP_RATE_WINDOW_SECONDS = env_int(
    "DCC_DIAGNOSTIC_STOP_RATE_WINDOW_SECONDS", 60
)
DCC_DIAGNOSTIC_TARGET_COOLDOWN_SECONDS = env_int(
    "DCC_DIAGNOSTIC_TARGET_COOLDOWN_SECONDS", 0, minimum=0
)
DCC_METRICS_PROVIDER = os.environ.get(
    "DCC_METRICS_PROVIDER", "cloudwatch"
).strip().lower()
DCC_CLOUDWATCH_REGION = os.environ.get(
    "DCC_CLOUDWATCH_REGION", AWS_REGION
).strip()
DCC_CLOUDWATCH_CLUSTER_NAME = os.environ.get(
    "DCC_CLOUDWATCH_CLUSTER_NAME", ""
).strip()
DCC_CLOUDWATCH_SERVICE_NAME = os.environ.get(
    "DCC_CLOUDWATCH_SERVICE_NAME", ""
).strip()
DCC_CLOUDWATCH_ECS_NAMESPACE = os.environ.get(
    "DCC_CLOUDWATCH_ECS_NAMESPACE", ""
).strip()
DCC_CLOUDWATCH_CONTAINER_INSIGHTS_NAMESPACE = os.environ.get(
    "DCC_CLOUDWATCH_CONTAINER_INSIGHTS_NAMESPACE", ""
).strip()
DCC_PROMETHEUS_URL = os.environ.get("DCC_PROMETHEUS_URL", "").strip()
DCC_DEPENDENCIES_PROVIDER = os.environ.get(
    "DCC_DEPENDENCIES_PROVIDER", "cloudwatch"
).strip().lower()
DCC_DEPENDENCY_RESOURCES = os.environ.get(
    "DCC_DEPENDENCY_RESOURCES", "[]"
).strip()
DCC_LOGS_PROVIDER = os.environ.get("DCC_LOGS_PROVIDER", "loki").strip().lower()
DCC_LOKI_URL = os.environ.get("DCC_LOKI_URL", "").strip()
DCC_LOKI_BEARER_TOKEN = os.environ.get("DCC_LOKI_BEARER_TOKEN", "").strip()
DCC_LOKI_TENANT_ID = os.environ.get("DCC_LOKI_TENANT_ID", "").strip()

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "apps.health",
    "apps.api",
    "apps.diagnostics",
]

MIDDLEWARE = [
    "apps.health.middleware.LoadBalancerHealthHostMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "apps.api.security_headers.ApiContentSecurityPolicyMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/assets/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [
    str(BASE_DIR.parent / "frontend" / "dist"),
]
WHITENOISE_STATIC_PREFIX = "/"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "UNAUTHENTICATED_USER": None,
    "UNAUTHENTICATED_TOKEN": None,
    "EXCEPTION_HANDLER": "apps.api.exceptions.safe_exception_handler",
}

_cors_origins = os.environ.get("DCC_CORS_ALLOWED_ORIGINS")
if not DEBUG and not _cors_origins:
    raise ImproperlyConfigured(
        "DCC_CORS_ALLOWED_ORIGINS must be set when DJANGO_DEBUG is disabled."
    )
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in (
        _cors_origins
        if _cors_origins is not None
        else "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]
if "*" in CORS_ALLOWED_ORIGINS:
    raise ImproperlyConfigured(
        "DCC_CORS_ALLOWED_ORIGINS must not contain a wildcard."
    )
if not DEBUG and any(not origin.startswith("https://") for origin in CORS_ALLOWED_ORIGINS):
    raise ImproperlyConfigured(
        "Production DCC_CORS_ALLOWED_ORIGINS entries must use HTTPS."
    )
CORS_ALLOW_CREDENTIALS = False
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
CORS_URLS_REGEX = (
    r"^/api/(?:health/?|diagnostic-sessions/.*|ecs/(?:clusters|tasks)(?:/.*)?|services/?|tasks/(?:[^/]+/resources/)?|dependencies/?|logs/?|diagnostic-impact/?)$"
)
