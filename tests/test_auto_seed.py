from __future__ import annotations

from collections.abc import AsyncIterator
import json
from pathlib import Path

import httpx
import pytest
from sqlalchemy.orm import Session

from app.core.config import DEFAULT_AUTO_SEED_PATH, get_settings, load_settings
from app.main import app, create_app, run_auto_seed
from app.models import KnowledgeCard
from app.repositories import KnowledgeCardRepository
from app.schemas.knowledge_card import KnowledgeCardCreate
from app.services.seed import seed_knowledge_cards_if_empty

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
    app.dependency_overrides.clear()


@pytest.fixture()
async def client(db_session: Session) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as async_client:
            yield async_client
    app.dependency_overrides.clear()


def create_existing_card(db_session: Session) -> KnowledgeCard:
    repository = KnowledgeCardRepository(db_session)
    return repository.create(
        KnowledgeCardCreate(
            title="Existing card",
            category="python",
            core_knowledge="Existing core knowledge.",
            question="Existing question?",
            reference_answer="Existing reference answer.",
        )
    )


def test_auto_seed_imports_week_one_cards_when_database_is_empty(
    db_session: Session,
) -> None:
    created_count = seed_knowledge_cards_if_empty(db_session, DEFAULT_AUTO_SEED_PATH)

    assert created_count == 95
    assert KnowledgeCardRepository(db_session).count() == 95


def test_auto_seed_does_not_duplicate_when_cards_exist(db_session: Session) -> None:
    create_existing_card(db_session)

    created_count = seed_knowledge_cards_if_empty(db_session, DEFAULT_AUTO_SEED_PATH)

    assert created_count == 0
    assert KnowledgeCardRepository(db_session).count() == 1


def test_auto_seed_can_be_disabled(db_session: Session) -> None:
    settings = load_settings(
        {
            "OFFERFORGE_TESTING": "true",
            "OFFERFORGE_AUTO_SEED_ON_STARTUP": "false",
        }
    )

    created_count = run_auto_seed(settings)

    assert created_count == 0
    assert KnowledgeCardRepository(db_session).count() == 0


def test_auto_seed_missing_file_returns_zero(
    db_session: Session,
    tmp_path: Path,
) -> None:
    missing_path = tmp_path / "missing_seed.json"

    created_count = seed_knowledge_cards_if_empty(db_session, missing_path)

    assert created_count == 0
    assert KnowledgeCardRepository(db_session).count() == 0


def test_auto_seed_invalid_json_returns_zero(
    db_session: Session,
    tmp_path: Path,
) -> None:
    invalid_json_path = tmp_path / "invalid_seed.json"
    invalid_json_path.write_text("{not-valid-json", encoding="utf-8")

    created_count = seed_knowledge_cards_if_empty(db_session, invalid_json_path)

    assert created_count == 0
    assert KnowledgeCardRepository(db_session).count() == 0


def test_auto_seed_invalid_schema_returns_zero(
    db_session: Session,
    tmp_path: Path,
) -> None:
    invalid_schema_path = tmp_path / "invalid_schema_seed.json"
    invalid_schema_path.write_text(
        json.dumps(
            [
                {
                    "title": "Invalid seed card",
                    "category": "not_a_category",
                    "core_knowledge": "Invalid category.",
                    "question": "Will this validate?",
                    "reference_answer": "No.",
                }
            ]
        ),
        encoding="utf-8",
    )

    created_count = seed_knowledge_cards_if_empty(db_session, invalid_schema_path)

    assert created_count == 0
    assert KnowledgeCardRepository(db_session).count() == 0


async def test_auto_seeded_cards_are_available_for_today_reviews(
    client: httpx.AsyncClient,
    db_session: Session,
) -> None:
    created_count = seed_knowledge_cards_if_empty(db_session, DEFAULT_AUTO_SEED_PATH)

    response = await client.get("/api/v1/reviews/today")

    assert created_count == 95
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "new"
    assert data["total"] == 95
    assert len(data["items"]) == 10


async def test_lifespan_runs_auto_seed_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    monkeypatch.setenv("OFFERFORGE_AUTO_SEED_ON_STARTUP", "true")
    monkeypatch.setenv("OFFERFORGE_AUTO_SEED_PATH", str(DEFAULT_AUTO_SEED_PATH))
    get_settings.cache_clear()

    application = create_app()
    async with application.router.lifespan_context(application):
        assert KnowledgeCardRepository(db_session).count() == 95
