from __future__ import annotations

from sqlalchemy.exc import IntegrityError

from app.models import KnowledgeCard
from app.models.enums import (
    DifficultyLevel,
    KnowledgeCategory,
    MasteryLevel,
    QuestionType,
)
from app.repositories import KnowledgeCardRepository, PracticeAttemptRepository
from app.schemas.knowledge_card import (
    KnowledgeCardCreate,
    KnowledgeCardSourceActiveUpdateResponse,
    KnowledgeCardSourceDeleteResponse,
    KnowledgeCardSourceSummary,
    KnowledgeCardUpdate,
)
from app.services.exceptions import (
    DuplicateKnowledgeCardError,
    KnowledgeCardSourceHasAttemptsError,
    KnowledgeCardNotFoundError,
    KnowledgeCardSourceNotFoundError,
)


def _is_card_identity_unique_constraint_error(exc: IntegrityError) -> bool:
    message = str(exc.orig) if exc.orig is not None else str(exc)
    source_aware_constraint = (
        "UNIQUE constraint failed: "
        "knowledge_cards.source_reference, knowledge_cards.category, "
        "knowledge_cards.title"
    )
    legacy_constraint = (
        "UNIQUE constraint failed: "
        "knowledge_cards.category, knowledge_cards.title"
    )
    return source_aware_constraint in message or legacy_constraint in message


class KnowledgeCardService:
    def __init__(
        self,
        repository: KnowledgeCardRepository,
        attempt_repository: PracticeAttemptRepository | None = None,
    ) -> None:
        self.repository = repository
        self.attempt_repository = attempt_repository

    def create_card(self, data: KnowledgeCardCreate) -> KnowledgeCard:
        self._ensure_unique_card_identity(data)
        return self._create_card_without_precheck(data)

    def create_cards(
        self,
        items: list[KnowledgeCardCreate],
    ) -> list[KnowledgeCard]:
        seen_identities: set[
            tuple[str | None, KnowledgeCategory, str]
        ] = set()
        for item in items:
            identity = (item.source_reference, item.category, item.title)
            if identity in seen_identities:
                raise DuplicateKnowledgeCardError(
                    item.category,
                    item.title,
                    item.source_reference,
                )
            seen_identities.add(identity)
            self._ensure_unique_card_identity(item)

        return [self._create_card_without_precheck(item) for item in items]

    def _ensure_unique_card_identity(self, data: KnowledgeCardCreate) -> None:
        if self.repository.exists_by_source_category_and_title(
            data.source_reference,
            data.category,
            data.title,
        ):
            raise DuplicateKnowledgeCardError(
                data.category,
                data.title,
                data.source_reference,
            )

    def _create_card_without_precheck(
        self,
        data: KnowledgeCardCreate,
    ) -> KnowledgeCard:
        try:
            return self.repository.create(data)
        except IntegrityError as exc:
            if _is_card_identity_unique_constraint_error(exc):
                raise DuplicateKnowledgeCardError(
                    data.category,
                    data.title,
                    data.source_reference,
                ) from exc
            raise

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

    def delete_source_reference(
        self,
        source_reference: str,
    ) -> KnowledgeCardSourceDeleteResponse:
        card_ids = self.repository.list_ids_by_source_reference(source_reference)
        if not card_ids:
            raise KnowledgeCardSourceNotFoundError(source_reference)

        if self.attempt_repository is None:
            raise RuntimeError("Practice attempt repository is required.")

        attempts_count = self.attempt_repository.count_by_knowledge_card_ids(card_ids)
        if attempts_count > 0:
            raise KnowledgeCardSourceHasAttemptsError(source_reference)

        deleted_count = self.repository.delete_by_source_reference(source_reference)
        return KnowledgeCardSourceDeleteResponse(
            source_reference=source_reference,
            deleted_count=deleted_count,
        )

    def update_card(
        self,
        card_id: int,
        data: KnowledgeCardUpdate,
    ) -> KnowledgeCard:
        card = self.get_card(card_id)
        updated_fields = data.model_dump(exclude_unset=True)
        changes_identity = any(
            field_name in updated_fields
            for field_name in ("source_reference", "category", "title")
        )

        final_source_reference = (
            data.source_reference
            if "source_reference" in updated_fields
            else card.source_reference
        )
        final_category = (
            data.category if "category" in updated_fields else card.category
        )
        final_title = data.title if "title" in updated_fields else card.title

        if changes_identity and self.repository.exists_by_source_category_and_title(
            final_source_reference,
            final_category,
            final_title,
            exclude_id=card.id,
        ):
            raise DuplicateKnowledgeCardError(
                final_category,
                final_title,
                final_source_reference,
            )

        try:
            return self.repository.update(card, data)
        except IntegrityError as exc:
            if _is_card_identity_unique_constraint_error(exc):
                raise DuplicateKnowledgeCardError(
                    final_category,
                    final_title,
                    final_source_reference,
                ) from exc
            raise

    def delete_card(self, card_id: int) -> None:
        card = self.get_card(card_id)
        self.repository.delete(card)
