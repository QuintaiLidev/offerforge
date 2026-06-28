from __future__ import annotations

from datetime import timedelta

from app.models.time import utc_now
from app.repositories import KnowledgeCardRepository, PracticeAttemptRepository
from app.schemas.review import (
    DoneTodayReviewItem,
    DoneTodayReviewResponse,
    ReviewTodayResponse,
)


class ReviewService:
    def __init__(
        self,
        card_repository: KnowledgeCardRepository,
        attempt_repository: PracticeAttemptRepository,
    ) -> None:
        self.card_repository = card_repository
        self.attempt_repository = attempt_repository

    def get_today_reviews(self, limit: int = 10) -> ReviewTodayResponse:
        if limit < 1 or limit > 50:
            raise ValueError("limit must be between 1 and 50.")

        generated_at = utc_now()
        due_cards, due_total = self.card_repository.list_due_for_review(
            generated_at,
            limit=limit,
        )
        if due_cards:
            return ReviewTodayResponse(
                mode="due",
                items=due_cards,
                total=due_total,
                limit=limit,
                generated_at=generated_at,
            )

        new_cards, new_total = self.card_repository.list_new_for_review(limit=limit)
        return ReviewTodayResponse(
            mode="new",
            items=new_cards,
            total=new_total,
            limit=limit,
            generated_at=generated_at,
        )

    def get_done_today_reviews(self, limit: int = 20) -> DoneTodayReviewResponse:
        if limit < 1 or limit > 50:
            raise ValueError("limit must be between 1 and 50.")

        now = utc_now()
        start_at = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_at = start_at + timedelta(days=1)
        rows = self.attempt_repository.list_latest_attempts_by_card_for_period(
            start_at=start_at,
            end_at=end_at,
            limit=limit,
        )
        return DoneTodayReviewResponse(
            items=[
                DoneTodayReviewItem(card=card, latest_attempt=latest_attempt)
                for card, latest_attempt in rows
            ]
        )
