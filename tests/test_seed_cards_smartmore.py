from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.models.enums import KnowledgeCategory
from app.schemas.knowledge_card import KnowledgeCardCreate

SEED_PATH = Path("data_seed/cards_seed_smartmore_interview_v1.json")
EXPECTED_COUNT = 15
EXPECTED_SOURCE_REFERENCE = "interview-smartmore-v1"
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
ALLOWED_CATEGORIES = {category.value for category in KnowledgeCategory}
SENSITIVE_TERMS = (
    "password",
    "passwd",
    "token",
    "secret",
    "api_key",
    "access_key",
    "jdbc:",
    "mongodb://",
    "postgres://",
    "mysql://",
)


def load_seed_cards() -> list[dict[str, Any]]:
    return json.loads(SEED_PATH.read_text(encoding="utf-8"))


def test_smartmore_seed_file_exists_and_is_valid_json() -> None:
    assert SEED_PATH.exists()
    assert isinstance(load_seed_cards(), list)


def test_smartmore_seed_file_contains_15_cards() -> None:
    assert len(load_seed_cards()) == EXPECTED_COUNT


def test_smartmore_seed_cards_validate_as_knowledge_card_create() -> None:
    for card in load_seed_cards():
        KnowledgeCardCreate.model_validate(card)


def test_smartmore_seed_cards_have_expected_source_reference() -> None:
    for card in load_seed_cards():
        assert card["source_reference"] == EXPECTED_SOURCE_REFERENCE


def test_smartmore_seed_cards_use_existing_categories_only() -> None:
    for card in load_seed_cards():
        assert card["category"] in ALLOWED_CATEGORIES


def test_smartmore_seed_cards_have_required_non_empty_content() -> None:
    for card in load_seed_cards():
        assert REQUIRED_FIELDS <= card.keys()
        for field in ("title", "question", "reference_answer", "core_knowledge"):
            assert isinstance(card[field], str)
            assert card[field].strip()
        assert isinstance(card["tags"], list)
        assert card["tags"]
        assert all(isinstance(tag, str) and tag.strip() for tag in card["tags"])


def test_smartmore_seed_cards_do_not_contain_sensitive_terms() -> None:
    seed_text = SEED_PATH.read_text(encoding="utf-8").lower()
    for term in SENSITIVE_TERMS:
        assert term not in seed_text
