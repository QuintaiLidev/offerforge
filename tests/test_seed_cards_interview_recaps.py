from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from app.models.enums import KnowledgeCategory
from app.schemas.knowledge_card import KnowledgeCardCreate


SEED_FILES = {
    Path("data_seed/cards_seed_tidong_interview_v1.json"): {
        "count": 10,
        "source_reference": "interview-tidong-20260706-v1",
    },
    Path("data_seed/cards_seed_pengzhirui_interview_v1.json"): {
        "count": 13,
        "source_reference": "interview-pengzhirui-20260707-v1",
    },
}
EXPECTED_TOTAL_COUNT = 23
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
    "被开除",
    "公司睡觉",
    "公司太压榨",
    "API Key 值",
    "数据库密码",
    "连接串明文",
)


def load_seed_cards(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def all_recap_cards() -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for path in SEED_FILES:
        cards.extend(load_seed_cards(path))
    return cards


def test_interview_recap_seed_files_exist_and_are_valid_json() -> None:
    for path in SEED_FILES:
        assert path.exists()
        cards = load_seed_cards(path)
        assert isinstance(cards, list)
        assert all(isinstance(card, dict) for card in cards)


def test_interview_recap_seed_files_have_expected_counts() -> None:
    for path, expected in SEED_FILES.items():
        assert len(load_seed_cards(path)) == expected["count"]

    assert len(all_recap_cards()) == EXPECTED_TOTAL_COUNT


def test_interview_recap_seed_cards_validate_as_knowledge_card_create() -> None:
    for card in all_recap_cards():
        KnowledgeCardCreate.model_validate(card)


def test_interview_recap_seed_cards_have_expected_source_references() -> None:
    for path, expected in SEED_FILES.items():
        for card in load_seed_cards(path):
            assert card["source_reference"] == expected["source_reference"]


def test_interview_recap_seed_cards_use_existing_categories_only() -> None:
    for card in all_recap_cards():
        assert card["category"] in ALLOWED_CATEGORIES


def test_interview_recap_seed_cards_have_required_non_empty_content() -> None:
    for card in all_recap_cards():
        assert REQUIRED_FIELDS <= card.keys()
        for field in ("title", "question", "reference_answer", "core_knowledge"):
            assert isinstance(card[field], str)
            assert card[field].strip()
        assert isinstance(card["scoring_rules"], dict)
        assert card["scoring_rules"]
        assert isinstance(card["scoring_rules"].get("must_include"), list)
        assert card["scoring_rules"]["must_include"]
        assert isinstance(card["scoring_rules"].get("good_to_include"), list)
        assert card["scoring_rules"]["good_to_include"]
        assert isinstance(card["tags"], list)
        assert card["tags"]
        assert all(isinstance(tag, str) and tag.strip() for tag in card["tags"])


def test_interview_recap_seed_card_titles_are_unique_within_each_file() -> None:
    for path in SEED_FILES:
        title_counts = Counter(card["title"] for card in load_seed_cards(path))

        assert [title for title, count in title_counts.items() if count > 1] == []


def test_interview_recap_seed_cards_do_not_contain_sensitive_terms() -> None:
    for path in SEED_FILES:
        seed_text = path.read_text(encoding="utf-8").lower()
        for term in SENSITIVE_TERMS:
            assert term not in seed_text
