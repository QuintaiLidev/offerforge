from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
import hashlib

from app.models import KnowledgeCard
from app.models.time import utc_now
from app.repositories import KnowledgeCardRepository, PracticeAttemptRepository
from app.schemas.review import (
    DoneTodayReviewItem,
    DoneTodayReviewResponse,
    PracticeHistoryItem,
    PracticeHistoryResponse,
    ReviewTodayResponse,
)


def _category_value(card: KnowledgeCard) -> str:
    category = card.category
    return category.value if hasattr(category, "value") else str(category)


def daily_shuffle_key(today: date, namespace: str, value: str) -> str:
    raw = f"{today.isoformat()}:{namespace}:{value}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def balance_cards_by_category(
    cards: list[KnowledgeCard],
    *,
    limit: int,
    today: date | None = None,
) -> list[KnowledgeCard]:
    if limit <= 0 or not cards:
        return []

    review_date = today or utc_now().date()
    grouped_cards: dict[str, list[KnowledgeCard]] = defaultdict(list)
    for card in cards:
        grouped_cards[_category_value(card)].append(card)

    categories = sorted(
        grouped_cards,
        key=lambda category: daily_shuffle_key(review_date, "category", category),
    )
    buckets = {
        category: sorted(
            category_cards,
            key=lambda card: (
                daily_shuffle_key(
                    review_date,
                    f"card:{category}",
                    str(card.id),
                ),
                card.id,
            ),
        )
        for category, category_cards in grouped_cards.items()
    }

    balanced_cards: list[KnowledgeCard] = []
    while len(balanced_cards) < limit:
        added_in_round = False
        for category in categories:
            if not buckets[category]:
                continue
            balanced_cards.append(buckets[category].pop(0))
            added_in_round = True
            if len(balanced_cards) >= limit:
                break
        if not added_in_round:
            break

    return balanced_cards


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
        review_date = generated_at.date()
        due_cards, due_total = self._list_due_candidates(
            generated_at=generated_at,
            requested_limit=limit,
        )
        balanced_due_cards = balance_cards_by_category(
            due_cards,
            limit=limit,
            today=review_date,
        )
        if len(balanced_due_cards) >= limit:
            return ReviewTodayResponse(
                mode="due",
                items=balanced_due_cards,
                total=due_total,
                limit=limit,
                generated_at=generated_at,
            )

        remaining_limit = limit - len(balanced_due_cards)
        new_cards, new_total = self._list_new_candidates(requested_limit=remaining_limit)
        balanced_new_cards = balance_cards_by_category(
            new_cards,
            limit=remaining_limit,
            today=review_date,
        )
        items = [*balanced_due_cards, *balanced_new_cards]

        return ReviewTodayResponse(
            mode="due" if due_total else "new",
            items=items,
            total=due_total + new_total,
            limit=limit,
            generated_at=generated_at,
        )

    def _list_due_candidates(
        self,
        *,
        generated_at: datetime,
        requested_limit: int,
    ) -> tuple[list[KnowledgeCard], int]:
        cards, total = self.card_repository.list_due_for_review(
            generated_at,
            limit=requested_limit,
        )
        if total > len(cards):
            cards, total = self.card_repository.list_due_for_review(
                generated_at,
                limit=total,
            )
        return cards, total

    def _list_new_candidates(
        self,
        *,
        requested_limit: int,
    ) -> tuple[list[KnowledgeCard], int]:
        if requested_limit <= 0:
            return [], 0

        cards, total = self.card_repository.list_new_for_review(limit=requested_limit)
        if total > len(cards):
            cards, total = self.card_repository.list_new_for_review(limit=total)
        return cards, total

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

    def get_practice_history(self, limit: int = 50) -> PracticeHistoryResponse:
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100.")

        rows = self.attempt_repository.list_recent_with_cards(limit=limit)
        return PracticeHistoryResponse(
            items=[
                PracticeHistoryItem(
                    attempt_id=attempt.id,
                    created_at=attempt.created_at,
                    rating=attempt.rating,
                    user_answer=attempt.user_answer,
                    scheduled_next_review_at=attempt.scheduled_next_review_at,
                    card=card,
                )
                for card, attempt in rows
            ]
        )
