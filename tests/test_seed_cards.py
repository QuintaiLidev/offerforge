from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from app.schemas.knowledge_card import KnowledgeCardCreate


SEED_PATH = Path("data_seed/cards_seed_week1_interview_v3.json")
EXPECTED_SOURCE_REFERENCE = "interview-week1-v3"
REQUIRED_FIELDS = {
    "title",
    "category",
    "difficulty",
    "question_type",
    "core_knowledge",
    "question",
    "reference_answer",
    "scoring_rules",
    "tags",
    "source_reference",
}
SENSITIVE_TERMS = ["password", "token", "secret", "api_key"]
FORBIDDEN_TOPICS = [
    "文件锁",
    "缩进问题",
    "Locust 文件锁",
    "报告文件被占用",
]


def load_seed_cards() -> list[dict[str, Any]]:
    return json.loads(SEED_PATH.read_text(encoding="utf-8"))


def test_week_one_seed_file_exists_and_is_valid_json() -> None:
    assert SEED_PATH.exists()

    cards = load_seed_cards()

    assert isinstance(cards, list)


def test_week_one_seed_file_contains_95_cards() -> None:
    cards = load_seed_cards()

    assert len(cards) == 95


def test_week_one_seed_cards_have_required_shape() -> None:
    cards = load_seed_cards()

    for card in cards:
        assert REQUIRED_FIELDS <= card.keys()
        assert isinstance(card["tags"], list)
        assert isinstance(card["scoring_rules"], dict)
        assert card["source_reference"] == EXPECTED_SOURCE_REFERENCE


def test_week_one_seed_cards_do_not_contain_sensitive_terms() -> None:
    seed_text = SEED_PATH.read_text(encoding="utf-8").lower()

    for term in SENSITIVE_TERMS:
        assert term not in seed_text


def test_week_one_seed_cards_validate_as_knowledge_card_create() -> None:
    cards = load_seed_cards()

    for card in cards:
        KnowledgeCardCreate.model_validate(card)


def test_week_one_seed_cards_do_not_include_deferred_topics() -> None:
    seed_text = SEED_PATH.read_text(encoding="utf-8")

    for topic in FORBIDDEN_TOPICS:
        assert topic not in seed_text


def test_week_one_seed_cards_keep_expected_category_distribution() -> None:
    cards = load_seed_cards()

    assert Counter(card["category"] for card in cards) == {
        "real_business_case": 18,
        "project_explanation": 16,
        "selenium": 10,
        "python": 12,
        "sql": 8,
        "linux_git_ci": 8,
        "hr_interview": 8,
        "http_api_testing": 15,
    }
