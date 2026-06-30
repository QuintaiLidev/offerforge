from __future__ import annotations

from collections import Counter, defaultdict
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
    practiced_category_counts: dict[str, int] | None = None,
    recent_practiced_categories: list[str] | None = None,
) -> list[KnowledgeCard]:
    if limit <= 0 or not cards:
        return []

    review_date = today or utc_now().date()
    grouped_cards: dict[str, list[KnowledgeCard]] = defaultdict(list)
    for card in cards:
        grouped_cards[_category_value(card)].append(card)

    buckets = {
        category: list(category_cards)
        for category, category_cards in grouped_cards.items()
    }
    practiced_counts = Counter(practiced_category_counts or {})
    recent_categories = list(recent_practiced_categories or [])

    def category_priority(category: str) -> tuple[int, int, int, str]:
        hard_recent_penalty = int(
            len(recent_categories) >= 2
            and recent_categories[0] == recent_categories[1] == category
        )
        soft_recent_penalty = int(
            bool(recent_categories) and recent_categories[0] == category
        )
        return (
            hard_recent_penalty,
            practiced_counts[category],
            soft_recent_penalty,
            daily_shuffle_key(review_date, "category", category),
        )

    balanced_cards: list[KnowledgeCard] = []
    while len(balanced_cards) < limit:
        available_categories = [
            category for category, category_cards in buckets.items() if category_cards
        ]
        if not available_categories:
            break
        category = min(available_categories, key=category_priority)
        balanced_cards.append(buckets[category].pop(0))
        practiced_counts[category] += 1
        recent_categories = [category, *recent_categories[:1]]

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
        practiced_categories = self._list_practiced_categories_for_today(generated_at)
        practiced_category_counts = dict(Counter(practiced_categories))
        due_cards, due_total = self._list_due_candidates(
            generated_at=generated_at,
            requested_limit=limit,
        )
        balanced_due_cards = balance_cards_by_category(
            due_cards,
            limit=limit,
            today=review_date,
            practiced_category_counts=practiced_category_counts,
            recent_practiced_categories=practiced_categories,
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
        items = balance_cards_by_category(
            [*balanced_due_cards, *new_cards],
            limit=limit,
            today=review_date,
            practiced_category_counts=practiced_category_counts,
            recent_practiced_categories=practiced_categories,
        )

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

    def _list_practiced_categories_for_today(
        self,
        generated_at: datetime,
    ) -> list[str]:
        start_at = generated_at.replace(hour=0, minute=0, second=0, microsecond=0)
        end_at = start_at + timedelta(days=1)
        return self.attempt_repository.list_practiced_categories_for_period(
            start_at=start_at,
            end_at=end_at,
        )

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
