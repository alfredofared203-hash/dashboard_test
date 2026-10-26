from api.config import get_settings
from api.dependencies import (
    get_redis_client,
    timed_redis_operation,
)


VALUE_KEY = "test-laboratory:value"
COUNTER_KEY = "test-laboratory:counter"
WORKER_KEY = "test-laboratory:worker-heartbeat"
KEY_TTL_SECONDS = 86_400


def get_value() -> str | None:
    return timed_redis_operation("get", lambda: get_redis_client().get(VALUE_KEY))


def set_value(value: str) -> None:
    def set_item() -> None:
        get_redis_client().set(VALUE_KEY, value, ex=KEY_TTL_SECONDS)

    timed_redis_operation("set", set_item)


def increment_counter() -> int:
    def increment() -> int:
        client = get_redis_client()
        value = client.incr(COUNTER_KEY)
        client.expire(COUNTER_KEY, KEY_TTL_SECONDS)
        return value

    return timed_redis_operation("increment", increment)


def worker_heartbeat() -> int:
    def increment() -> int:
        client = get_redis_client()
        value = client.incr(WORKER_KEY)
        client.expire(WORKER_KEY, KEY_TTL_SECONDS)
        return value

    return timed_redis_operation("worker_heartbeat", increment)


def redis_configured() -> bool:
    return bool(get_settings().redis_url)
