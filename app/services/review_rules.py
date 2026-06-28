from __future__ import annotations

from datetime import datetime, timedelta

from app.models.enums import MasteryLevel, PracticeRating
from app.models.time import utc_now

CORRECT_RATINGS: frozenset[PracticeRating] = frozenset(
    {
        PracticeRating.CORRECT_SLOW,
        PracticeRating.CORRECT_EXPLAIN,
        PracticeRating.TRANSFER,
    }
)
NEEDS_REVIEW_RATINGS: frozenset[PracticeRating] = frozenset(
    {
        PracticeRating.DONT_KNOW,
        PracticeRating.WITH_HINT,
    }
)


def is_correct_rating(rating: PracticeRating) -> bool:
    return rating in CORRECT_RATINGS


def calculate_next_review_at(
    rating: PracticeRating,
    practiced_at: datetime | None = None,
    consecutive_correct_count: int = 0,
) -> datetime:
    base_time = practiced_at or utc_now()
    next_consecutive_count = consecutive_correct_count + 1

    if rating is PracticeRating.DONT_KNOW:
        return base_time + timedelta(days=1)
    if rating is PracticeRating.WITH_HINT:
        return base_time + timedelta(days=1)
    if rating is PracticeRating.CORRECT_SLOW:
        return base_time + timedelta(days=2)
    if rating is PracticeRating.CORRECT_EXPLAIN:
        return base_time + timedelta(days=4)
    if rating is PracticeRating.TRANSFER:
        if next_consecutive_count == 1:
            return base_time + timedelta(days=7)
        if next_consecutive_count == 2:
            return base_time + timedelta(days=14)
        if next_consecutive_count == 3:
            return base_time + timedelta(days=30)
        return base_time + timedelta(days=60)
    return base_time + timedelta(days=1)


def calculate_mastery_level(
    rating: PracticeRating,
    consecutive_correct_count_after: int,
) -> MasteryLevel:
    if rating in {PracticeRating.DONT_KNOW, PracticeRating.WITH_HINT}:
        return MasteryLevel.LEARNING
    if rating is PracticeRating.CORRECT_SLOW:
        if consecutive_correct_count_after >= 2:
            return MasteryLevel.FAMILIAR
        return MasteryLevel.LEARNING
    if rating is PracticeRating.CORRECT_EXPLAIN:
        return MasteryLevel.FAMILIAR
    if consecutive_correct_count_after >= 3:
        return MasteryLevel.MASTERED
    return MasteryLevel.FAMILIAR
