from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.services.seed import seed_knowledge_cards_if_empty

SEED_PATHS = (
    Path("data_seed/cards_seed_week1_interview_v3.json"),
    Path("data_seed/cards_seed_week1_interview_v4.json"),
    Path("data_seed/cards_seed_pengzhirui_interview_v1.json"),
)
NON_VISIBLE_METADATA_FIELDS = {"id", "source_reference", "tags"}


def load_seed(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    return data


@pytest.mark.parametrize("seed_path", SEED_PATHS, ids=lambda path: path.stem)
def test_selected_seed_json_is_valid_and_uses_skillloop_brand(
    seed_path: Path,
) -> None:
    cards = load_seed(seed_path)
    assert cards

    visible_text = json.dumps(
        [
            {
                key: value
                for key, value in card.items()
                if key not in NON_VISIBLE_METADATA_FIELDS
            }
            for card in cards
        ],
        ensure_ascii=False,
    )
    assert "SkillLoop" in visible_text
    assert "OfferForge" not in visible_text


@pytest.mark.parametrize("seed_path", SEED_PATHS, ids=lambda path: path.stem)
def test_selected_seed_imports_into_an_empty_database(
    db_session: Session,
    seed_path: Path,
) -> None:
    expected_count = len(load_seed(seed_path))

    created_count = seed_knowledge_cards_if_empty(db_session, seed_path)

    assert created_count == expected_count
