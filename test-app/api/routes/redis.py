from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, StrictStr

from api.dependencies import DependencyUnavailable
from api.services.redis_service import get_value, increment_counter, set_value


router = APIRouter(prefix="/api")


class RedisValueRequest(BaseModel):
    value: StrictStr = Field(min_length=1, max_length=128)


@router.get("/redis")
def read_value() -> dict[str, str | int | None]:
    try:
        return {"value": get_value()}
    except DependencyUnavailable:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis is currently unavailable.",
        ) from None


@router.post("/redis")
def write_value(payload: RedisValueRequest | None = None) -> dict[str, object]:
    try:
        if payload is None:
            return {"counter": increment_counter()}
        set_value(payload.value)
        return {"stored": True, "value_length": len(payload.value)}
    except DependencyUnavailable:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis is currently unavailable.",
        ) from None
