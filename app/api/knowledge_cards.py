from __future__ import annotations

from typing import Annotated

from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Path,
    Query,
    Response,
    status,
)

from app.api.deps import get_knowledge_card_service
from app.models.enums import (
    DifficultyLevel,
    KnowledgeCategory,
    MasteryLevel,
    QuestionType,
)
from app.schemas.knowledge_card import (
    KnowledgeCardBulkCreateResponse,
    KnowledgeCardCreate,
    KnowledgeCardListResponse,
    KnowledgeCardRead,
    KnowledgeCardUpdate,
)
from app.services import (
    DuplicateKnowledgeCardError,
    KnowledgeCardNotFoundError,
    KnowledgeCardService,
)

router: APIRouter = APIRouter(prefix="/cards", tags=["Knowledge Cards"])

KnowledgeCardServiceDep = Annotated[
    KnowledgeCardService,
    Depends(get_knowledge_card_service),
]
CardIdPath = Annotated[int, Path(gt=0)]
BulkCreateBody = Annotated[
    list[KnowledgeCardCreate],
    Body(min_length=1, max_length=100),
]


@router.post(
    "",
    response_model=KnowledgeCardRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a knowledge card",
    responses={
        status.HTTP_409_CONFLICT: {"description": "Duplicate knowledge card title"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "Validation error"},
    },
)
def create_knowledge_card(
    data: KnowledgeCardCreate,
    service: KnowledgeCardServiceDep,
) -> KnowledgeCardRead:
    try:
        return service.create_card(data)
    except DuplicateKnowledgeCardError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.post(
    "/bulk",
    response_model=KnowledgeCardBulkCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Bulk create knowledge cards",
    responses={
        status.HTTP_409_CONFLICT: {"description": "Duplicate knowledge card title"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "Validation error"},
    },
)
def bulk_create_knowledge_cards(
    data: BulkCreateBody,
    service: KnowledgeCardServiceDep,
) -> KnowledgeCardBulkCreateResponse:
    try:
        items = service.create_cards(data)
    except DuplicateKnowledgeCardError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return KnowledgeCardBulkCreateResponse(created_count=len(items), items=items)


@router.get(
    "",
    response_model=KnowledgeCardListResponse,
    status_code=status.HTTP_200_OK,
    summary="List knowledge cards",
    responses={
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "Validation error"},
    },
)
def list_knowledge_cards(
    service: KnowledgeCardServiceDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    category: KnowledgeCategory | None = None,
    difficulty: DifficultyLevel | None = None,
    mastery_level: MasteryLevel | None = None,
    question_type: QuestionType | None = None,
    is_active: bool | None = None,
    keyword: str | None = None,
) -> KnowledgeCardListResponse:
    items, total = service.list_cards(
        offset=offset,
        limit=limit,
        category=category,
        difficulty=difficulty,
        mastery_level=mastery_level,
        question_type=question_type,
        is_active=is_active,
        keyword=keyword,
    )
    return KnowledgeCardListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{card_id}",
    response_model=KnowledgeCardRead,
    status_code=status.HTTP_200_OK,
    summary="Get a knowledge card",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Knowledge card not found"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "Validation error"},
    },
)
def get_knowledge_card(
    card_id: CardIdPath,
    service: KnowledgeCardServiceDep,
) -> KnowledgeCardRead:
    try:
        return service.get_card(card_id)
    except KnowledgeCardNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.patch(
    "/{card_id}",
    response_model=KnowledgeCardRead,
    status_code=status.HTTP_200_OK,
    summary="Update a knowledge card",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Knowledge card not found"},
        status.HTTP_409_CONFLICT: {"description": "Duplicate knowledge card title"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "Validation error"},
    },
)
def update_knowledge_card(
    card_id: CardIdPath,
    data: KnowledgeCardUpdate,
    service: KnowledgeCardServiceDep,
) -> KnowledgeCardRead:
    try:
        return service.update_card(card_id, data)
    except KnowledgeCardNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except DuplicateKnowledgeCardError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.delete(
    "/{card_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a knowledge card",
    response_class=Response,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Knowledge card not found"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "Validation error"},
    },
)
def delete_knowledge_card(
    card_id: CardIdPath,
    service: KnowledgeCardServiceDep,
) -> Response:
    try:
        service.delete_card(card_id)
    except KnowledgeCardNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
