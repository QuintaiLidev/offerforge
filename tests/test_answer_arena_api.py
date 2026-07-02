from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.main import app
from app.models import KnowledgeCard, PracticeAttempt
from app.models.enums import KnowledgeCategory
from app.repositories import KnowledgeCardRepository
from app.schemas.knowledge_card import KnowledgeCardCreate

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
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as async_client:
            yield async_client
    app.dependency_overrides.clear()


def create_card(db_session: Session, *, title: str = "AI 在测试领域怎么用？", category: KnowledgeCategory = KnowledgeCategory.PROJECT_EXPLANATION) -> KnowledgeCard:
    return KnowledgeCardRepository(db_session).create(
        KnowledgeCardCreate(
            title=title,
            category=category,
            core_knowledge="core",
            question=f"{title}?",
            reference_answer="【30秒口述版】AI 是提效工具，我会用它做初稿和需求拆解，但质量责任由我验证。",
            tags=["ai_tools"],
        )
    )


async def test_score_api_requires_auth_when_enabled(monkeypatch: pytest.MonkeyPatch, client: httpx.AsyncClient) -> None:
    monkeypatch.setenv("OFFERFORGE_AUTH_ENABLED", "true")
    monkeypatch.setenv("OFFERFORGE_AUTH_USERNAME", "offerforge")
    monkeypatch.setenv("OFFERFORGE_AUTH_PASSWORD", "test-secret")
    get_settings.cache_clear()

    response = await client.post("/api/v1/answer-arena/score", json={"card_id": 1, "user_answer": "我的理解是需要先正面回答问题，然后补充两个结构化要点，再结合项目接口权限或回归例子，最后总结岗位匹配和质量风险。"})

    assert response.status_code == 401


async def test_score_api_returns_404_for_missing_card(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/v1/answer-arena/score", json={"card_id": 999, "user_answer": "我的理解是需要先正面回答问题，然后补充两个结构化要点，再结合项目接口权限或回归例子，最后总结岗位匹配和质量风险。"})

    assert response.status_code == 404


@pytest.mark.parametrize("answer", ["", "太短"])
async def test_score_api_rejects_empty_or_too_short_answer(client: httpx.AsyncClient, db_session: Session, answer: str) -> None:
    card = create_card(db_session)

    response = await client.post("/api/v1/answer-arena/score", json={"card_id": card.id, "user_answer": answer})

    assert response.status_code == 422


async def test_score_api_returns_score_and_does_not_write_attempt_or_card(client: httpx.AsyncClient, db_session: Session) -> None:
    card = create_card(db_session)
    before = {
        "title": card.title,
        "mastery_level": card.mastery_level,
        "next_review_at": card.next_review_at,
        "consecutive_correct_count": card.consecutive_correct_count,
        "total_error_count": card.total_error_count,
        "updated_at": card.updated_at,
    }

    response = await client.post(
        "/api/v1/answer-arena/score",
        json={
            "card_id": card.id,
            "user_answer": "我的理解是 AI 是提效工具。第一可以做需求拆解和初稿，第二我负责验证质量，比如接口自动化后还要做测试回归和调试验证，最后质量责任仍然在我。",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert 0 <= data["total_score"] <= 100
    assert len(data["dimension_scores"]) == 7
    assert data["optimized_answer_30s"]
    assert db_session.scalar(select(PracticeAttempt).where(PracticeAttempt.knowledge_card_id == card.id)) is None
    db_session.refresh(card)
    assert card.title == before["title"]
    assert card.mastery_level == before["mastery_level"]
    assert card.next_review_at == before["next_review_at"]
    assert card.consecutive_correct_count == before["consecutive_correct_count"]
    assert card.total_error_count == before["total_error_count"]
    assert card.updated_at == before["updated_at"]


async def test_score_api_detects_ai_risk_expression(client: httpx.AsyncClient, db_session: Session) -> None:
    card = create_card(db_session, title="Cursor 你用过吗？")

    response = await client.post(
        "/api/v1/answer-arena/score",
        json={"card_id": card.id, "user_answer": "我的理解是 Cursor 很好用，AI 写了 80%，主要都是 AI 写的，我让 AI 做，然后自己看一下。"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "AI 写了 80%" in data["risk_expressions"]
    assert data["dimension_scores"]["risk_control"] < 6
