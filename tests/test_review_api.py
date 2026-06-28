from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.main import app, create_app
from app.models import KnowledgeCard
from app.models.enums import KnowledgeCategory, MasteryLevel
from app.repositories import KnowledgeCardRepository
from app.schemas.knowledge_card import KnowledgeCardCreate

pytestmark = pytest.mark.anyio

FIXED_NOW = datetime(2026, 6, 27, 12, 0, 0)


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


def make_card_create(
    *,
    title: str,
    category: KnowledgeCategory = KnowledgeCategory.PYTHON,
) -> KnowledgeCardCreate:
    return KnowledgeCardCreate(
        title=title,
        category=category,
        core_knowledge=f"Core knowledge for {title}",
        question=f"Question about {title}",
        reference_answer=f"Reference answer for {title}",
    )


def create_card(
    db_session: Session,
    *,
    title: str,
    category: KnowledgeCategory = KnowledgeCategory.PYTHON,
    **overrides: Any,
) -> KnowledgeCard:
    repository = KnowledgeCardRepository(db_session)
    card = repository.create(make_card_create(title=title, category=category))
    for field_name, value in overrides.items():
        setattr(card, field_name, value)
    if overrides:
        db_session.commit()
        db_session.refresh(card)
    return card


def item_ids(data: dict[str, Any]) -> list[int]:
    return [item["id"] for item in data["items"]]


def item_categories(data: dict[str, Any]) -> list[str]:
    return [item["category"] for item in data["items"]]


async def test_today_returns_due_cards_when_available(
    client: httpx.AsyncClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    due_card = create_card(
        db_session,
        title="Due card",
        mastery_level=MasteryLevel.LEARNING,
        next_review_at=FIXED_NOW - timedelta(hours=1),
    )
    new_card = create_card(db_session, title="New fallback card")
    monkeypatch.setattr("app.services.review.utc_now", lambda: FIXED_NOW)

    response = await client.get("/api/v1/reviews/today")

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "due"
    assert data["limit"] == 10
    assert data["total"] == 2
    assert item_ids(data) == [due_card.id, new_card.id]
    assert data["generated_at"] == FIXED_NOW.isoformat()


async def test_today_due_condition_includes_equal_now_and_excludes_future(
    client: httpx.AsyncClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    past_due = create_card(
        db_session,
        title="Past due",
        mastery_level=MasteryLevel.LEARNING,
        next_review_at=FIXED_NOW - timedelta(days=1),
    )
    due_now = create_card(
        db_session,
        title="Due now",
        mastery_level=MasteryLevel.FAMILIAR,
        next_review_at=FIXED_NOW,
    )
    future = create_card(
        db_session,
        title="Future review",
        mastery_level=MasteryLevel.FAMILIAR,
        next_review_at=FIXED_NOW + timedelta(seconds=1),
    )
    monkeypatch.setattr("app.services.review.utc_now", lambda: FIXED_NOW)

    response = await client.get("/api/v1/reviews/today")

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "due"
    assert set(item_ids(data)) == {past_due.id, due_now.id}
    assert future.id not in item_ids(data)


async def test_today_excludes_inactive_cards(
    client: httpx.AsyncClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inactive_due = create_card(
        db_session,
        title="Inactive due",
        next_review_at=FIXED_NOW - timedelta(days=1),
        is_active=False,
    )
    active_new = create_card(db_session, title="Active new")
    monkeypatch.setattr("app.services.review.utc_now", lambda: FIXED_NOW)

    response = await client.get("/api/v1/reviews/today")

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "new"
    assert item_ids(data) == [active_new.id]
    assert inactive_due.id not in item_ids(data)


async def test_today_returns_new_cards_when_no_due_cards_exist(
    client: httpx.AsyncClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    older_new = create_card(
        db_session,
        title="Older new",
        created_at=FIXED_NOW - timedelta(days=2),
    )
    newer_new = create_card(
        db_session,
        title="Newer new",
        created_at=FIXED_NOW - timedelta(days=1),
    )
    create_card(
        db_session,
        title="Familiar not new",
        mastery_level=MasteryLevel.FAMILIAR,
    )
    monkeypatch.setattr("app.services.review.utc_now", lambda: FIXED_NOW)

    response = await client.get("/api/v1/reviews/today")

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "new"
    assert data["total"] == 2
    assert set(item_ids(data)) == {older_new.id, newer_new.id}


async def test_today_due_cards_reaching_limit_prevent_new_fallback(
    client: httpx.AsyncClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    due_cards = [
        create_card(
            db_session,
            title=f"Due wins {index}",
            category=KnowledgeCategory.PYTHON
            if index % 2
            else KnowledgeCategory.SQL,
            mastery_level=MasteryLevel.LEARNING,
            next_review_at=FIXED_NOW - timedelta(hours=2),
        )
        for index in range(5)
    ]
    new_card = create_card(db_session, title="New fallback skipped")
    monkeypatch.setattr("app.services.review.utc_now", lambda: FIXED_NOW)

    response = await client.get("/api/v1/reviews/today", params={"limit": 5})

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "due"
    assert set(item_ids(data)) == {card.id for card in due_cards}
    assert new_card.id not in item_ids(data)


async def test_today_due_cards_are_followed_by_new_cards_when_due_is_short(
    client: httpx.AsyncClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    due_cards = [
        create_card(
            db_session,
            title="Due Python",
            category=KnowledgeCategory.PYTHON,
            mastery_level=MasteryLevel.LEARNING,
            next_review_at=FIXED_NOW - timedelta(hours=2),
        ),
        create_card(
            db_session,
            title="Due SQL",
            category=KnowledgeCategory.SQL,
            mastery_level=MasteryLevel.LEARNING,
            next_review_at=FIXED_NOW - timedelta(hours=1),
        ),
        create_card(
            db_session,
            title="Due Selenium",
            category=KnowledgeCategory.SELENIUM,
            mastery_level=MasteryLevel.LEARNING,
            next_review_at=FIXED_NOW,
        ),
    ]
    new_cards = [
        create_card(
            db_session,
            title=f"New card {index}",
            category=category,
        )
        for index, category in enumerate(
            [
                KnowledgeCategory.PYTHON,
                KnowledgeCategory.SQL,
                KnowledgeCategory.SELENIUM,
                KnowledgeCategory.HTTP_API_TESTING,
                KnowledgeCategory.REAL_BUSINESS_CASE,
            ]
        )
    ]
    monkeypatch.setattr("app.services.review.utc_now", lambda: FIXED_NOW)

    response = await client.get("/api/v1/reviews/today", params={"limit": 6})

    assert response.status_code == 200
    data = response.json()
    ids = item_ids(data)
    assert data["mode"] == "due"
    assert set(ids[:3]) == {card.id for card in due_cards}
    assert set(ids[3:]) <= {card.id for card in new_cards}
    assert len(ids[3:]) == 3


async def test_today_balances_categories_and_is_stable_within_day(
    client: httpx.AsyncClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    categories = [
        KnowledgeCategory.PYTHON,
        KnowledgeCategory.SQL,
        KnowledgeCategory.SELENIUM,
        KnowledgeCategory.HTTP_API_TESTING,
        KnowledgeCategory.REAL_BUSINESS_CASE,
    ]
    created_ids: list[int] = []
    for category in categories:
        for index in range(3):
            card = create_card(
                db_session,
                title=f"{category.value} card {index}",
                category=category,
                created_at=FIXED_NOW + timedelta(seconds=len(created_ids)),
            )
            created_ids.append(card.id)
    monkeypatch.setattr("app.services.review.utc_now", lambda: FIXED_NOW)

    first = await client.get("/api/v1/reviews/today", params={"limit": 10})
    second = await client.get("/api/v1/reviews/today", params={"limit": 10})

    assert first.status_code == 200
    assert second.status_code == 200
    first_data = first.json()
    second_data = second.json()
    assert item_ids(first_data) == item_ids(second_data)
    assert item_ids(first_data) != created_ids[:10]
    assert len(set(item_categories(first_data))) == len(categories)
    assert len(first_data["items"]) == 10


async def test_today_single_category_returns_all_candidates_when_under_limit(
    client: httpx.AsyncClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cards = [
        create_card(db_session, title=f"Single category {index}")
        for index in range(3)
    ]
    monkeypatch.setattr("app.services.review.utc_now", lambda: FIXED_NOW)

    response = await client.get("/api/v1/reviews/today", params={"limit": 10})

    assert response.status_code == 200
    data = response.json()
    assert set(item_ids(data)) == {card.id for card in cards}
    assert item_categories(data) == ["python", "python", "python"]


async def test_today_default_limit_returns_ten_items(
    client: httpx.AsyncClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for index in range(11):
        create_card(
            db_session,
            title=f"New card {index}",
            created_at=FIXED_NOW + timedelta(seconds=index),
        )
    monkeypatch.setattr("app.services.review.utc_now", lambda: FIXED_NOW)

    response = await client.get("/api/v1/reviews/today")

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "new"
    assert data["limit"] == 10
    assert data["total"] == 11
    assert len(data["items"]) == 10


@pytest.mark.parametrize("limit", [0, 51])
async def test_today_rejects_invalid_limit(
    client: httpx.AsyncClient,
    limit: int,
) -> None:
    response = await client.get("/api/v1/reviews/today", params={"limit": limit})

    assert response.status_code == 422


async def test_today_auth_and_health_behavior_when_auth_enabled(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    create_card(db_session, title="Auth new card")
    monkeypatch.setenv("OFFERFORGE_AUTH_ENABLED", "true")
    monkeypatch.setenv("OFFERFORGE_AUTH_USERNAME", "offerforge")
    monkeypatch.setenv("OFFERFORGE_AUTH_PASSWORD", "test-secret")
    monkeypatch.setattr("app.services.review.utc_now", lambda: FIXED_NOW)
    get_settings.cache_clear()

    application = create_app()
    transport = httpx.ASGITransport(app=application)
    async with application.router.lifespan_context(application):
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as auth_client:
            health = await auth_client.get("/api/v1/health")
            without_auth = await auth_client.get("/api/v1/reviews/today")
            with_auth = await auth_client.get(
                "/api/v1/reviews/today",
                auth=("offerforge", "test-secret"),
            )

    assert health.status_code == 200
    assert without_auth.status_code == 401
    assert without_auth.headers["www-authenticate"] == "Basic"
    assert with_auth.status_code == 200


async def test_today_does_not_modify_knowledge_card_data(
    client: httpx.AsyncClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    card = create_card(
        db_session,
        title="Read only due card",
        mastery_level=MasteryLevel.LEARNING,
        next_review_at=FIXED_NOW - timedelta(days=1),
        consecutive_correct_count=3,
        total_error_count=2,
    )
    before = {
        "mastery_level": card.mastery_level,
        "last_practiced_at": card.last_practiced_at,
        "next_review_at": card.next_review_at,
        "consecutive_correct_count": card.consecutive_correct_count,
        "total_error_count": card.total_error_count,
        "is_active": card.is_active,
        "updated_at": card.updated_at,
    }
    monkeypatch.setattr("app.services.review.utc_now", lambda: FIXED_NOW)

    response = await client.get("/api/v1/reviews/today")

    assert response.status_code == 200
    db_session.expire_all()
    refreshed = db_session.get(KnowledgeCard, card.id)
    assert refreshed is not None
    after = {
        "mastery_level": refreshed.mastery_level,
        "last_practiced_at": refreshed.last_practiced_at,
        "next_review_at": refreshed.next_review_at,
        "consecutive_correct_count": refreshed.consecutive_correct_count,
        "total_error_count": refreshed.total_error_count,
        "is_active": refreshed.is_active,
        "updated_at": refreshed.updated_at,
    }
    assert after == before
