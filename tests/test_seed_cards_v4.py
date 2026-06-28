from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.schemas.knowledge_card import KnowledgeCardCreate


SEED_PATH = Path("data_seed/cards_seed_week1_interview_v4.json")
EXPECTED_COUNT = 95
EXPECTED_SOURCE_REFERENCE = "interview-week1-v4"
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
ALLOWED_CATEGORIES = {
    "real_business_case",
    "project_explanation",
    "selenium",
    "python",
    "sql",
    "linux_git_ci",
    "hr_interview",
    "http_api_testing",
}
REFERENCE_ANSWER_MARKERS = {
    "【30秒口述】",
    "【记忆钩子】",
    "【展开回答】",
    "【追问防守】",
}
SENSITIVE_TERMS = ("password", "token", "secret", "api_key")
FORBIDDEN_TOPICS = ("Locust 文件锁", "报告文件被占用", "缩进问题")


def load_seed_cards() -> list[dict[str, Any]]:
    return json.loads(SEED_PATH.read_text(encoding="utf-8-sig"))


def test_week_one_v4_seed_file_exists_and_is_valid_json() -> None:
    assert SEED_PATH.exists()

    cards = load_seed_cards()

    assert isinstance(cards, list)


def test_week_one_v4_seed_file_contains_95_cards() -> None:
    cards = load_seed_cards()

    assert len(cards) == EXPECTED_COUNT


def test_week_one_v4_seed_cards_have_required_shape() -> None:
    cards = load_seed_cards()

    for card in cards:
        assert REQUIRED_FIELDS <= card.keys()
        assert card["source_reference"] == EXPECTED_SOURCE_REFERENCE
        assert isinstance(card["tags"], list)
        assert isinstance(card["scoring_rules"], dict)
        assert card["category"] in ALLOWED_CATEGORIES


def test_week_one_v4_seed_cards_validate_as_knowledge_card_create() -> None:
    cards = load_seed_cards()

    for card in cards:
        KnowledgeCardCreate.model_validate(card)


def test_week_one_v4_reference_answers_are_detailed_and_structured() -> None:
    cards = load_seed_cards()

    missing_structure = []
    short_answers = []
    for card in cards:
        reference_answer = card["reference_answer"].strip()
        marker_count = sum(marker in reference_answer for marker in REFERENCE_ANSWER_MARKERS)
        if len(reference_answer) < 200:
            short_answers.append(card["title"])
        if marker_count < 2:
            missing_structure.append(card["title"])

    assert short_answers == []
    assert missing_structure == []


def test_week_one_v4_seed_cards_do_not_contain_sensitive_terms() -> None:
    seed_text = SEED_PATH.read_text(encoding="utf-8-sig").lower()

    for term in SENSITIVE_TERMS:
        assert term not in seed_text


def test_week_one_v4_seed_cards_do_not_include_deferred_topics() -> None:
    seed_text = SEED_PATH.read_text(encoding="utf-8-sig")

    for topic in FORBIDDEN_TOPICS:
        assert topic not in seed_text
