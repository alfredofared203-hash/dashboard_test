from fastapi import APIRouter, HTTPException, Query, status
from pydantic import StrictInt

from api.dependencies import DependencyUnavailable
from api.services.database_service import list_orders, list_products


router = APIRouter(prefix="/api")


@router.get("/products")
def products(limit: StrictInt = Query(default=10, ge=1, le=25)) -> dict[str, object]:
    try:
        return {"items": list_products(limit)}
    except DependencyUnavailable:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PostgreSQL is currently unavailable.",
        ) from None


@router.get("/orders")
def orders(limit: StrictInt = Query(default=10, ge=1, le=25)) -> dict[str, object]:
    try:
        return {"items": list_orders(limit)}
    except DependencyUnavailable:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PostgreSQL is currently unavailable.",
        ) from None
