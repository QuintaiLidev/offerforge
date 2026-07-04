from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_answer_arena_service
from app.core.config import Settings, get_settings
from app.main import app
from app.models import KnowledgeCard, PracticeAttempt
from app.models.enums import KnowledgeCategory
from app.repositories import KnowledgeCardRepository
from app.schemas.answer_arena import ANSWER_SCORE_DIMENSIONS, AnswerScoreResponse
from app.schemas.knowledge_card import KnowledgeCardCreate
from app.services.answer_arena import AnswerArenaService
from app.services.exceptions import (
    AiScoringInvalidResponseError,
    AiScoringTimeoutError,
)

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


class FakeAiProvider:
    def score(self, *, card: KnowledgeCard, user_answer: str) -> AnswerScoreResponse:
        return AnswerScoreResponse(
            provider="openai",
            total_score=91,
            dimension_scores={dimension: 9 for dimension in ANSWER_SCORE_DIMENSIONS},
            strengths=["specific"],
            problems=[],
            risk_expressions=[],
            suggestions=["keep it concise"],
            optimized_answer_30s="AI optimized answer.",
            memory_labels=["ai"],
            missing_points=["缺少具体例子"],
            complete_answer="完整参考答案：先给结论，再结合接口自动化项目说明验证链路和风险边界。",
            concrete_examples=[
                "pytest 示例：\nassert response.status_code == 200\nassert response.json()['code'] == '0000'"
            ],
            interview_answer_60s="我会先说明结论，再讲接口、数据和项目落点，最后补充风险边界。",
            interview_answer_30s="接口自动化要验证响应、数据库和业务状态，并说明风险边界。",
            follow_up_questions=["你怎么做数据库断言？", "接口失败怎么定位？"],
            follow_up_qas=[
                "Q：你怎么做数据库断言？\nA：我会先拿业务唯一标识查库，再核对状态、数量和关键字段。"
            ],
            next_practice_step="下次用 login -> create_user -> db assert 讲一遍项目链路。",
        )


class FakeOpenRouterProvider:
    def score(self, *, card: KnowledgeCard, user_answer: str) -> AnswerScoreResponse:
        return AnswerScoreResponse(
            provider="openrouter",
            total_score=93,
            dimension_scores={dimension: 9 for dimension in ANSWER_SCORE_DIMENSIONS},
            strengths=["specific"],
            problems=[],
            risk_expressions=[],
            suggestions=["keep it concise"],
            optimized_answer_30s="OpenRouter optimized answer.",
            memory_labels=["openrouter"],
            missing_points=["缺少真实项目表达"],
            complete_answer="完整参考答案：结合 OfferForge 和接口自动化项目说明做法、验证和边界。",
            concrete_examples=["SQL 断言示例：\nselect status from users where id = :user_id;"],
            interview_answer_60s="我会用一分钟讲清目标、实现、验证和风险边界。",
            interview_answer_30s="用项目链路说明测试开发能力，重点讲验证闭环。",
            follow_up_questions=["这个项目怎么证明不是玩具？"],
            follow_up_qas=[
                "Q：这个项目怎么证明不是玩具？\nA：我会从可运行、可测试、可复盘三个点说明。"
            ],
            next_practice_step="下次用 30 秒讲清 SQL 断言层。",
        )


class TimeoutAiProvider:
    def score(self, *, card: KnowledgeCard, user_answer: str) -> AnswerScoreResponse:
        raise AiScoringTimeoutError("AI scoring provider timed out.")


class InvalidAiProvider:
    def score(self, *, card: KnowledgeCard, user_answer: str) -> AnswerScoreResponse:
        raise AiScoringInvalidResponseError("AI scoring response was invalid.")


async def test_score_api_rule_mode_returns_rule_provider(
    client: httpx.AsyncClient,
    db_session: Session,
) -> None:
    card = create_card(db_session)

    response = await client.post(
        "/api/v1/answer-arena/score",
        json={
            "card_id": card.id,
            "mode": "rule",
            "user_answer": "This answer is long enough and includes a structured project example for scoring.",
        },
    )

    assert response.status_code == 200
    assert response.json()["provider"] == "rule"


async def test_score_api_ai_mode_uses_mocked_provider(
    client: httpx.AsyncClient,
    db_session: Session,
) -> None:
    card = create_card(db_session)

    def override_service() -> AnswerArenaService:
        return AnswerArenaService(
            KnowledgeCardRepository(db_session),
            ai_provider=FakeAiProvider(),
            settings=Settings(openai_api_key="test-key"),
        )

    app.dependency_overrides[get_answer_arena_service] = override_service

    response = await client.post(
        "/api/v1/answer-arena/score",
        json={
            "card_id": card.id,
            "mode": "ai",
            "user_answer": "This answer is long enough and includes a structured project example for scoring.",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "openai"
    assert data["total_score"] == 91
    assert data["missing_points"] == ["缺少具体例子"]
    assert data["complete_answer"].startswith("完整参考答案")
    assert "assert response.status_code == 200" in data["concrete_examples"][0]
    assert data["interview_answer_60s"].startswith("我会先说明结论")
    assert data["interview_answer_30s"].startswith("接口自动化")
    assert data["follow_up_questions"] == ["你怎么做数据库断言？", "接口失败怎么定位？"]
    assert data["follow_up_qas"][0].startswith("Q：你怎么做数据库断言")
    assert data["next_practice_step"].startswith("下次用 login")
    assert db_session.scalar(
        select(PracticeAttempt).where(PracticeAttempt.knowledge_card_id == card.id)
    ) is None


async def test_score_api_ai_mode_without_key_returns_503(
    client: httpx.AsyncClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    get_settings.cache_clear()
    card = create_card(db_session)

    response = await client.post(
        "/api/v1/answer-arena/score",
        json={
            "card_id": card.id,
            "mode": "ai",
            "user_answer": "This answer is long enough and includes a structured project example for scoring.",
        },
    )

    assert response.status_code == 503


async def test_score_api_openrouter_mode_without_key_returns_503(
    client: httpx.AsyncClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OFFERFORGE_AI_SCORE_BACKEND", "openrouter")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    get_settings.cache_clear()
    card = create_card(db_session)

    response = await client.post(
        "/api/v1/answer-arena/score",
        json={
            "card_id": card.id,
            "mode": "ai",
            "user_answer": "This answer is long enough and includes a structured project example for scoring.",
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "OpenRouter API key is not configured."


async def test_score_api_openrouter_mode_uses_mocked_provider_without_mutation(
    client: httpx.AsyncClient,
    db_session: Session,
) -> None:
    card = create_card(db_session)
    before = {
        "title": card.title,
        "question": card.question,
        "reference_answer": card.reference_answer,
        "mastery_level": card.mastery_level,
        "next_review_at": card.next_review_at,
        "last_practiced_at": card.last_practiced_at,
        "consecutive_correct_count": card.consecutive_correct_count,
        "total_error_count": card.total_error_count,
        "updated_at": card.updated_at,
    }

    def override_service() -> AnswerArenaService:
        return AnswerArenaService(
            KnowledgeCardRepository(db_session),
            ai_provider=FakeOpenRouterProvider(),
            settings=Settings(
                ai_score_backend="openrouter",
                openrouter_api_key="test-router-key",
            ),
        )

    app.dependency_overrides[get_answer_arena_service] = override_service

    response = await client.post(
        "/api/v1/answer-arena/score",
        json={
            "card_id": card.id,
            "mode": "ai",
            "user_answer": "This answer is long enough and includes a structured project example for scoring.",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "openrouter"
    assert data["total_score"] == 93
    assert db_session.scalar(
        select(PracticeAttempt).where(PracticeAttempt.knowledge_card_id == card.id)
    ) is None
    db_session.refresh(card)
    assert card.title == before["title"]
    assert card.question == before["question"]
    assert card.reference_answer == before["reference_answer"]
    assert card.mastery_level == before["mastery_level"]
    assert card.next_review_at == before["next_review_at"]
    assert card.last_practiced_at == before["last_practiced_at"]
    assert card.consecutive_correct_count == before["consecutive_correct_count"]
    assert card.total_error_count == before["total_error_count"]
    assert card.updated_at == before["updated_at"]


async def test_score_api_ai_timeout_returns_504(
    client: httpx.AsyncClient,
    db_session: Session,
) -> None:
    card = create_card(db_session)

    def override_service() -> AnswerArenaService:
        return AnswerArenaService(
            KnowledgeCardRepository(db_session),
            ai_provider=TimeoutAiProvider(),
            settings=Settings(openai_api_key="test-key"),
        )

    app.dependency_overrides[get_answer_arena_service] = override_service

    response = await client.post(
        "/api/v1/answer-arena/score",
        json={
            "card_id": card.id,
            "mode": "ai",
            "user_answer": "This answer is long enough and includes a structured project example for scoring.",
        },
    )

    assert response.status_code == 504


async def test_score_api_ai_invalid_response_returns_503(
    client: httpx.AsyncClient,
    db_session: Session,
) -> None:
    card = create_card(db_session)

    def override_service() -> AnswerArenaService:
        return AnswerArenaService(
            KnowledgeCardRepository(db_session),
            ai_provider=InvalidAiProvider(),
            settings=Settings(openai_api_key="test-key"),
        )

    app.dependency_overrides[get_answer_arena_service] = override_service

    response = await client.post(
        "/api/v1/answer-arena/score",
        json={
            "card_id": card.id,
            "mode": "ai",
            "user_answer": "This answer is long enough and includes a structured project example for scoring.",
        },
    )

    assert response.status_code == 503
