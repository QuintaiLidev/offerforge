from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import PRODUCT_NAME


class HealthResponse(BaseModel):
    status: str
    service: str


router: APIRouter = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(status="ok", service=PRODUCT_NAME)
