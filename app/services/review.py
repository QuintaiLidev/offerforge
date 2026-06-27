from __future__ import annotations

from app.models.time import utc_now
from app.repositories import KnowledgeCardRepository
from app.schemas.review import ReviewTodayResponse


class ReviewService:
    def __init__(self, card_repository: KnowledgeCardRepository) -> None:
        self.card_repository = card_repository

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
