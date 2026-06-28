from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_review_service
from app.schemas.review import DoneTodayReviewResponse, ReviewTodayResponse
from app.services import ReviewService

router: APIRouter = APIRouter(prefix="/reviews", tags=["Reviews"])

ReviewServiceDep = Annotated[ReviewService, Depends(get_review_service)]


@router.get(
    "/today",
    response_model=ReviewTodayResponse,
    status_code=status.HTTP_200_OK,
    summary="Get today's review cards",
    responses={
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "Validation error"},
    },
)
def get_today_reviews(
    service: ReviewServiceDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> ReviewTodayResponse:
    return service.get_today_reviews(limit=limit)


@router.get(
    "/done-today",
    response_model=DoneTodayReviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Get cards practiced today",
    responses={
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "Validation error"},
    },
)
def get_done_today_reviews(
    service: ReviewServiceDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> DoneTodayReviewResponse:
    return service.get_done_today_reviews(limit=limit)
