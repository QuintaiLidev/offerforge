from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_answer_arena_service
from app.schemas.answer_arena import AnswerScoreRequest, AnswerScoreResponse
from app.services import (
    AiScoringInvalidResponseError,
    AiScoringTimeoutError,
    AiScoringUnavailableError,
    KnowledgeCardNotFoundError,
)
from app.services.answer_arena import AnswerArenaService

router: APIRouter = APIRouter(prefix="/answer-arena", tags=["Answer Arena"])

AnswerArenaServiceDep = Annotated[AnswerArenaService, Depends(get_answer_arena_service)]


@router.post(
    "/score",
    response_model=AnswerScoreResponse,
    status_code=status.HTTP_200_OK,
    summary="Score a practice answer with rules or optional AI",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Knowledge card not found"},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "AI scoring unavailable"},
        status.HTTP_504_GATEWAY_TIMEOUT: {"description": "AI scoring timeout"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "Validation error"},
    },
)
def score_answer(
    data: AnswerScoreRequest,
    service: AnswerArenaServiceDep,
) -> AnswerScoreResponse:
    try:
        return service.score_answer(
            card_id=data.card_id,
            user_answer=data.user_answer,
            mode=data.mode,
        )
    except KnowledgeCardNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (AiScoringUnavailableError, AiScoringInvalidResponseError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except AiScoringTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=str(exc),
        ) from exc
