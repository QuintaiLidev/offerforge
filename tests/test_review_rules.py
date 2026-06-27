from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.models.enums import MasteryLevel, PracticeRating
from app.services.review_rules import (
    calculate_mastery_level,
    calculate_next_review_at,
    is_correct_rating,
)


@pytest.mark.parametrize(
    ("rating", "consecutive_before", "expected_delta"),
    [
        (PracticeRating.DONT_KNOW, 0, timedelta(days=1)),
        (PracticeRating.WITH_HINT, 0, timedelta(days=2)),
        (PracticeRating.CORRECT_SLOW, 0, timedelta(days=4)),
        (PracticeRating.CORRECT_EXPLAIN, 0, timedelta(days=7)),
        (PracticeRating.TRANSFER, 0, timedelta(days=14)),
        (PracticeRating.TRANSFER, 1, timedelta(days=30)),
    ],
)
def test_calculate_next_review_at_uses_five_rating_rules(
    rating: PracticeRating,
    consecutive_before: int,
    expected_delta: timedelta,
) -> None:
    practiced_at = datetime(2026, 6, 27, 12, 0, 0)

    result = calculate_next_review_at(
        rating,
        practiced_at=practiced_at,
        consecutive_correct_count=consecutive_before,
    )

    assert result == practiced_at + expected_delta
    assert result.tzinfo is None


def test_calculate_next_review_at_defaults_to_utc_naive_now() -> None:
    result = calculate_next_review_at(PracticeRating.DONT_KNOW)

    assert result.tzinfo is None


@pytest.mark.parametrize(
    ("rating", "consecutive_after", "expected"),
    [
        (PracticeRating.DONT_KNOW, 0, MasteryLevel.LEARNING),
        (PracticeRating.WITH_HINT, 0, MasteryLevel.LEARNING),
        (PracticeRating.CORRECT_SLOW, 1, MasteryLevel.FAMILIAR),
        (PracticeRating.CORRECT_EXPLAIN, 1, MasteryLevel.PROFICIENT),
        (PracticeRating.TRANSFER, 1, MasteryLevel.PROFICIENT),
        (PracticeRating.TRANSFER, 2, MasteryLevel.MASTERED),
    ],
)
def test_calculate_mastery_level(
    rating: PracticeRating,
    consecutive_after: int,
    expected: MasteryLevel,
) -> None:
    assert calculate_mastery_level(rating, consecutive_after) is expected


@pytest.mark.parametrize(
    ("rating", "expected"),
    [
        (PracticeRating.DONT_KNOW, False),
        (PracticeRating.WITH_HINT, False),
        (PracticeRating.CORRECT_SLOW, True),
        (PracticeRating.CORRECT_EXPLAIN, True),
        (PracticeRating.TRANSFER, True),
    ],
)
def test_is_correct_rating(rating: PracticeRating, expected: bool) -> None:
    assert is_correct_rating(rating) is expected
