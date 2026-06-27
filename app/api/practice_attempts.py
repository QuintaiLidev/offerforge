from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_practice_attempt_service
from app.schemas.practice_attempt import (
    PracticeAttemptCompleteResponse,
    PracticeAttemptCreate,
)
from app.services import KnowledgeCardNotFoundError, PracticeAttemptService

router: APIRouter = APIRouter(
    prefix="/practice-attempts",
    tags=["Practice Attempts"],
)

PracticeAttemptServiceDep = Annotated[
    PracticeAttemptService,
    Depends(get_practice_attempt_service),
]


@router.post(
    "",
    response_model=PracticeAttemptCompleteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Complete a practice attempt",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Knowledge card not found"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "Validation error"},
    },
)
def complete_practice_attempt(
    data: PracticeAttemptCreate,
    service: PracticeAttemptServiceDep,
) -> PracticeAttemptCompleteResponse:
    try:
        attempt, card = service.complete_practice(data)
    except KnowledgeCardNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return PracticeAttemptCompleteResponse(attempt=attempt, card=card)
