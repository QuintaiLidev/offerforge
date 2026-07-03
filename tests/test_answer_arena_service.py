from __future__ import annotations

import pytest

from app.core.config import Settings
from app.models.enums import KnowledgeCategory
from app.repositories import KnowledgeCardRepository
from app.schemas.answer_arena import ANSWER_SCORE_DIMENSIONS, AnswerScoreResponse
from app.schemas.knowledge_card import KnowledgeCardCreate
from app.services.answer_score_provider import (
    OpenAIAnswerScoreProvider,
    parse_ai_score_payload,
)
from app.services.answer_arena import AnswerArenaService
from app.services.exceptions import (
    AiScoringInvalidResponseError,
    AiScoringTimeoutError,
    AiScoringUnavailableError,
)


def create_card(db_session, *, title: str, category: KnowledgeCategory, reference_answer: str = "【30秒口述版】先结论，再讲两个要点，一个例子，最后收尾。", tags: list[str] | None = None):
    return KnowledgeCardRepository(db_session).create(
        KnowledgeCardCreate(
            title=title,
            category=category,
            core_knowledge="core",
            question=f"{title}?",
            reference_answer=reference_answer,
            tags=tags or [],
        )
    )


def test_service_returns_total_score_and_seven_dimensions(db_session) -> None:
    card = create_card(db_session, title="AI 在测试领域怎么用？", category=KnowledgeCategory.PROJECT_EXPLANATION, tags=["ai_tools"])
    service = AnswerArenaService(KnowledgeCardRepository(db_session))

    result = service.score_answer(
        card_id=card.id,
        user_answer="我的理解是 AI 是提效工具。第一可以做需求拆解和初稿，第二我负责验证质量，比如接口自动化后还要做测试回归和调试验证，最后质量责任仍然在我。",
    )

    assert 0 <= result.total_score <= 100
    assert result.provider == "rule"
    assert set(result.dimension_scores) == {
        "direct_answer",
        "structure",
        "real_example",
        "job_match",
        "boundary",
        "professional_expression",
        "risk_control",
    }


def test_service_detects_risk_expression_and_lowers_risk_control(db_session) -> None:
    card = create_card(db_session, title="Cursor 你用过吗？", category=KnowledgeCategory.PROJECT_EXPLANATION, tags=["ai_tools"])
    service = AnswerArenaService(KnowledgeCardRepository(db_session))

    result = service.score_answer(
        card_id=card.id,
        user_answer="我的理解是这个工具很好用，主要都是 AI 写的，AI 写了 80%，我让 AI 做，然后我再跑一下结果，差不多吧。",
    )

    assert "AI 写了 80%" in result.risk_expressions
    assert "主要都是 AI 写的" in result.risk_expressions
    assert result.dimension_scores["risk_control"] < 6


def test_ui_automation_keywords_score_higher_than_shallow_answer(db_session) -> None:
    card = create_card(db_session, title="UI 自动化是怎么做的？", category=KnowledgeCategory.SELENIUM, tags=["ui_automation"])
    service = AnswerArenaService(KnowledgeCardRepository(db_session))

    strong = service.score_answer(
        card_id=card.id,
        user_answer="我的理解是 UI 自动化要先选高价值流程。第一做录制初稿后进行定位优化，第二补等待处理、断言和稳定性维护，比如权限页面会用稳定属性减少 XPath 脆弱性。",
    )
    weak = service.score_answer(
        card_id=card.id,
        user_answer="我的理解是 UI 自动化就是先打开页面，然后跑一下脚本，遇到失败就改一下 XPath，最后能跑起来就可以。",
    )

    assert strong.total_score > weak.total_score
    assert strong.dimension_scores["job_match"] > weak.dimension_scores["job_match"]


def test_career_python_automation_risk_is_detected(db_session) -> None:
    card = create_card(db_session, title="你以后是想做 Python 自动化吗？", category=KnowledgeCategory.HR_INTERVIEW)
    service = AnswerArenaService(KnowledgeCardRepository(db_session))

    result = service.score_answer(
        card_id=card.id,
        user_answer="我的理解是我就是想做 Python 自动化，其他方向我不太清楚，因为外包没发展，公司做不了更深入的事情。",
    )

    assert "想做 Python 自动化" in result.risk_expressions
    assert "外包没发展" in result.risk_expressions

class FakeAiScoreProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[int, str]] = []

    def score(self, *, card, user_answer: str) -> AnswerScoreResponse:
        self.calls.append((card.id, user_answer))
        return AnswerScoreResponse(
            provider="openai",
            total_score=88,
            dimension_scores={dimension: 8 for dimension in ANSWER_SCORE_DIMENSIONS},
            strengths=["clear structure"],
            problems=["needs one sharper example"],
            risk_expressions=[],
            suggestions=["add a concrete project detail"],
            optimized_answer_30s="A concise AI-scored answer.",
            memory_labels=["structure"],
        )


def test_service_can_score_with_injected_ai_provider(db_session) -> None:
    card = create_card(
        db_session,
        title="AI scoring",
        category=KnowledgeCategory.PROJECT_EXPLANATION,
    )
    provider = FakeAiScoreProvider()
    service = AnswerArenaService(
        KnowledgeCardRepository(db_session),
        ai_provider=provider,
        settings=Settings(openai_api_key="test-key"),
    )

    result = service.score_answer(
        card_id=card.id,
        mode="ai",
        user_answer="This answer is long enough and uses a structured project example.",
    )

    assert result.provider == "openai"
    assert result.total_score == 88
    assert provider.calls == [
        (card.id, "This answer is long enough and uses a structured project example.")
    ]


def test_service_rejects_ai_mode_without_openai_key(db_session) -> None:
    card = create_card(
        db_session,
        title="AI scoring without key",
        category=KnowledgeCategory.PROJECT_EXPLANATION,
    )
    service = AnswerArenaService(
        KnowledgeCardRepository(db_session),
        settings=Settings(openai_api_key=None),
    )

    with pytest.raises(AiScoringUnavailableError):
        service.score_answer(
            card_id=card.id,
            mode="ai",
            user_answer="This answer is long enough and structured for scoring.",
        )


def test_ai_score_payload_parser_rejects_missing_dimensions() -> None:
    with pytest.raises(AiScoringInvalidResponseError):
        parse_ai_score_payload(
            {
                "total_score": 70,
                "dimension_scores": {"direct_answer": 7},
                "strengths": [],
                "problems": [],
                "risk_expressions": [],
                "suggestions": [],
                "optimized_answer_30s": "summary",
                "memory_labels": [],
            },
            provider="openai",
        )


class FakeAuthenticationError(Exception):
    pass


class FakePermissionDeniedError(Exception):
    pass


class FakeRateLimitError(Exception):
    pass


class FakeBadRequestError(Exception):
    pass


class FakeApiConnectionError(Exception):
    pass


class FakeApiStatusError(Exception):
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__("provider response should not leak")


class FakeApiTimeoutError(Exception):
    pass


class FakeCompletions:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    def create(self, **kwargs):
        raise self.exc


class FakeChat:
    def __init__(self, exc: Exception) -> None:
        self.completions = FakeCompletions(exc)


class FakeOpenAIClient:
    def __init__(self, exc: Exception) -> None:
        self.chat = FakeChat(exc)


def make_openai_provider_raising(exc: Exception) -> OpenAIAnswerScoreProvider:
    provider = OpenAIAnswerScoreProvider.__new__(OpenAIAnswerScoreProvider)
    provider._authentication_error = FakeAuthenticationError
    provider._permission_denied_error = FakePermissionDeniedError
    provider._rate_limit_error = FakeRateLimitError
    provider._bad_request_error = FakeBadRequestError
    provider._api_connection_error = FakeApiConnectionError
    provider._api_status_error = FakeApiStatusError
    provider._timeout_error = FakeApiTimeoutError
    provider._client = FakeOpenAIClient(exc)
    provider._model = "fake-model"
    return provider


@pytest.mark.parametrize(
    ("exc", "expected_error", "message"),
    [
        (
            FakeAuthenticationError("bad real-key"),
            AiScoringUnavailableError,
            "AI scoring authentication failed. Check OPENAI_API_KEY.",
        ),
        (
            FakePermissionDeniedError("denied"),
            AiScoringUnavailableError,
            "AI scoring permission denied. Check project permissions.",
        ),
        (
            FakeRateLimitError("quota"),
            AiScoringUnavailableError,
            "AI scoring rate limited or quota exceeded.",
        ),
        (
            FakeBadRequestError("bad request"),
            AiScoringUnavailableError,
            "AI scoring request was rejected by provider. Check model and request format.",
        ),
        (
            FakeApiConnectionError("network"),
            AiScoringUnavailableError,
            "AI scoring provider connection failed.",
        ),
        (
            FakeApiStatusError(500),
            AiScoringUnavailableError,
            "AI scoring provider returned status 500.",
        ),
        (
            FakeApiTimeoutError("timeout"),
            AiScoringTimeoutError,
            "AI scoring provider timed out.",
        ),
    ],
)
def test_openai_provider_returns_safe_error_messages(
    db_session,
    exc: Exception,
    expected_error: type[Exception],
    message: str,
) -> None:
    card = create_card(
        db_session,
        title="AI provider error",
        category=KnowledgeCategory.PROJECT_EXPLANATION,
    )
    provider = make_openai_provider_raising(exc)
    user_answer = "This answer includes sensitive interview notes that must not leak."

    with pytest.raises(expected_error) as raised:
        provider.score(card=card, user_answer=user_answer)

    assert str(raised.value) == message
    assert user_answer not in str(raised.value)
    assert "real-key" not in str(raised.value)
    assert "provider response should not leak" not in str(raised.value)
