from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_answer_arena_service
from app.schemas.answer_arena import AnswerScoreRequest, AnswerScoreResponse
from app.services import KnowledgeCardNotFoundError
from app.services.answer_arena import AnswerArenaService

router: APIRouter = APIRouter(prefix="/answer-arena", tags=["Answer Arena"])

AnswerArenaServiceDep = Annotated[AnswerArenaService, Depends(get_answer_arena_service)]


@router.post(
    "/score",
    response_model=AnswerScoreResponse,
    status_code=status.HTTP_200_OK,
    summary="Score a practice answer with local rules",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Knowledge card not found"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "Validation error"},
    },
)
def score_answer(
    data: AnswerScoreRequest,
    service: AnswerArenaServiceDep,
) -> AnswerScoreResponse:
    try:
        return service.score_answer(card_id=data.card_id, user_answer=data.user_answer)
    except KnowledgeCardNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
