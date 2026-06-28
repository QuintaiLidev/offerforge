from __future__ import annotations

from sqlalchemy.exc import IntegrityError

from app.models import KnowledgeCard
from app.models.enums import (
    DifficultyLevel,
    KnowledgeCategory,
    MasteryLevel,
    QuestionType,
)
from app.repositories import KnowledgeCardRepository
from app.schemas.knowledge_card import (
    KnowledgeCardCreate,
    KnowledgeCardSourceActiveUpdateResponse,
    KnowledgeCardSourceSummary,
    KnowledgeCardUpdate,
)
from app.services.exceptions import (
    DuplicateKnowledgeCardError,
    KnowledgeCardNotFoundError,
    KnowledgeCardSourceNotFoundError,
)


def _is_category_title_unique_constraint_error(exc: IntegrityError) -> bool:
    message = str(exc.orig) if exc.orig is not None else str(exc)
    return (
        "UNIQUE constraint failed: "
        "knowledge_cards.category, knowledge_cards.title"
    ) in message


class KnowledgeCardService:
    def __init__(self, repository: KnowledgeCardRepository) -> None:
        self.repository = repository

    def create_card(self, data: KnowledgeCardCreate) -> KnowledgeCard:
        if self.repository.exists_by_category_and_title(data.category, data.title):
            raise DuplicateKnowledgeCardError(data.category, data.title)

        try:
            return self.repository.create(data)
        except IntegrityError as exc:
            if _is_category_title_unique_constraint_error(exc):
                raise DuplicateKnowledgeCardError(data.category, data.title) from exc
            raise

    def create_cards(
        self,
        items: list[KnowledgeCardCreate],
    ) -> list[KnowledgeCard]:
        return [self.create_card(item) for item in items]

    def get_card(self, card_id: int) -> KnowledgeCard:
        card = self.repository.get_by_id(card_id)
        if card is None:
            raise KnowledgeCardNotFoundError(card_id)
        return card

    def list_cards(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        category: KnowledgeCategory | None = None,
        difficulty: DifficultyLevel | None = None,
        mastery_level: MasteryLevel | None = None,
        question_type: QuestionType | None = None,
        is_active: bool | None = None,
        keyword: str | None = None,
    ) -> tuple[list[KnowledgeCard], int]:
        if offset < 0:
            raise ValueError("offset must be non-negative.")
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100.")

        return self.repository.list(
            offset=offset,
            limit=limit,
            category=category,
            difficulty=difficulty,
            mastery_level=mastery_level,
            question_type=question_type,
            is_active=is_active,
            keyword=keyword,
        )

    def list_source_summaries(self) -> list[KnowledgeCardSourceSummary]:
        return [
            KnowledgeCardSourceSummary(
                source_reference=source_reference,
                total_count=total_count,
                active_count=active_count,
                inactive_count=inactive_count,
            )
            for (
                source_reference,
                total_count,
                active_count,
                inactive_count,
            ) in self.repository.list_source_summaries()
        ]

    def set_active_by_source_reference(
        self,
        source_reference: str,
        *,
        is_active: bool,
    ) -> KnowledgeCardSourceActiveUpdateResponse:
        updated_count = self.repository.set_active_by_source_reference(
            source_reference,
            is_active=is_active,
        )
        if updated_count == 0:
            raise KnowledgeCardSourceNotFoundError(source_reference)

        return KnowledgeCardSourceActiveUpdateResponse(
            source_reference=source_reference,
            updated_count=updated_count,
            is_active=is_active,
        )

    def update_card(
        self,
        card_id: int,
        data: KnowledgeCardUpdate,
    ) -> KnowledgeCard:
        card = self.get_card(card_id)
        updated_fields = data.model_dump(exclude_unset=True)
        changes_identity = "category" in updated_fields or "title" in updated_fields

        final_category = (
            data.category if "category" in updated_fields else card.category
        )
        final_title = data.title if "title" in updated_fields else card.title

        if changes_identity and self.repository.exists_by_category_and_title(
            final_category,
            final_title,
            exclude_id=card.id,
        ):
            raise DuplicateKnowledgeCardError(final_category, final_title)

        try:
            return self.repository.update(card, data)
        except IntegrityError as exc:
            if _is_category_title_unique_constraint_error(exc):
                raise DuplicateKnowledgeCardError(final_category, final_title) from exc
            raise

    def delete_card(self, card_id: int) -> None:
        card = self.get_card(card_id)
        self.repository.delete(card)
