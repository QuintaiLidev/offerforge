from __future__ import annotations

from app.models import KnowledgeCard, PracticeAttempt
from app.models.enums import PracticeRating
from app.models.time import utc_now
from app.repositories import KnowledgeCardRepository, PracticeAttemptRepository
from app.schemas.practice_attempt import PracticeAttemptCreate
from app.services.exceptions import KnowledgeCardNotFoundError
from app.services.review_rules import (
    calculate_mastery_level,
    calculate_next_review_at,
    is_correct_rating,
)


class PracticeAttemptService:
    def __init__(
        self,
        attempt_repository: PracticeAttemptRepository,
        card_repository: KnowledgeCardRepository,
    ) -> None:
        self.attempt_repository = attempt_repository
        self.card_repository = card_repository

    def complete_practice(
        self,
        data: PracticeAttemptCreate,
    ) -> tuple[PracticeAttempt, KnowledgeCard]:
        card = self.card_repository.get_by_id(data.knowledge_card_id)
        if card is None:
            raise KnowledgeCardNotFoundError(data.knowledge_card_id)

        practiced_at = utc_now()
        rating_is_correct = is_correct_rating(data.rating)
        next_review_at = calculate_next_review_at(
            data.rating,
            practiced_at=practiced_at,
            consecutive_correct_count=card.consecutive_correct_count,
        )

        if rating_is_correct:
            consecutive_correct_count = card.consecutive_correct_count + 1
            total_error_count = card.total_error_count
        else:
            consecutive_correct_count = 0
            total_error_count = card.total_error_count + 1

        mastery_level = calculate_mastery_level(
            data.rating,
            consecutive_correct_count_after=consecutive_correct_count,
        )
        is_correct = data.is_correct if data.is_correct is not None else rating_is_correct
        used_hint = data.used_hint or data.rating is PracticeRating.WITH_HINT

        attempt_data = PracticeAttemptCreate(
            knowledge_card_id=data.knowledge_card_id,
            rating=data.rating,
            is_correct=is_correct,
            used_hint=used_hint,
            user_answer=data.user_answer,
            elapsed_seconds=data.elapsed_seconds,
            error_summary=data.error_summary,
            feedback=data.feedback,
            scheduled_next_review_at=next_review_at,
        )
        attempt = self.attempt_repository.create(attempt_data)

        card.last_practiced_at = practiced_at
        card.next_review_at = next_review_at
        card.consecutive_correct_count = consecutive_correct_count
        card.total_error_count = total_error_count
        card.mastery_level = mastery_level
        updated_card = self.card_repository.save(card)

        return attempt, updated_card
