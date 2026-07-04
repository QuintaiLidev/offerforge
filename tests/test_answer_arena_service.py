from __future__ import annotations

import pytest

from app.core.config import Settings
from app.models.enums import KnowledgeCategory
from app.repositories import KnowledgeCardRepository
from app.schemas.answer_arena import ANSWER_SCORE_DIMENSIONS, AnswerScoreResponse
from app.schemas.knowledge_card import KnowledgeCardCreate
from app.services import answer_arena as answer_arena_module
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


def test_service_uses_openrouter_backend(
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    card = create_card(
        db_session,
        title="OpenRouter scoring",
        category=KnowledgeCategory.PROJECT_EXPLANATION,
    )
    captured: dict[str, object] = {}

    class StubOpenRouterAnswerScoreProvider:
        def __init__(
            self,
            *,
            api_key: str,
            model: str,
            timeout_seconds: int,
            site_url: str | None,
            app_title: str | None,
        ) -> None:
            captured.update(
                {
                    "api_key": api_key,
                    "model": model,
                    "timeout_seconds": timeout_seconds,
                    "site_url": site_url,
                    "app_title": app_title,
                }
            )

        def score(self, *, card, user_answer: str) -> AnswerScoreResponse:
            captured["card_id"] = card.id
            captured["user_answer"] = user_answer
            return AnswerScoreResponse(
                provider="openrouter",
                total_score=86,
                dimension_scores={
                    dimension: 8 for dimension in ANSWER_SCORE_DIMENSIONS
                },
                strengths=["clear"],
                problems=[],
                risk_expressions=[],
                suggestions=["add one example"],
                optimized_answer_30s="OpenRouter optimized answer.",
                memory_labels=["openrouter"],
            )

    monkeypatch.setattr(
        answer_arena_module,
        "OpenRouterAnswerScoreProvider",
        StubOpenRouterAnswerScoreProvider,
    )
    service = AnswerArenaService(
        KnowledgeCardRepository(db_session),
        settings=Settings(
            ai_score_backend="openrouter",
            openrouter_api_key="router-key",
            openrouter_model="openrouter/model",
            openrouter_site_url="https://offerforge.example",
            openrouter_app_title="OfferForge Test",
            ai_score_timeout_seconds=15,
        ),
    )

    result = service.score_answer(
        card_id=card.id,
        mode="ai",
        user_answer="This answer is long enough for OpenRouter scoring.",
    )

    assert result.provider == "openrouter"
    assert captured == {
        "api_key": "router-key",
        "model": "openrouter/model",
        "timeout_seconds": 15,
        "site_url": "https://offerforge.example",
        "app_title": "OfferForge Test",
        "card_id": card.id,
        "user_answer": "This answer is long enough for OpenRouter scoring.",
    }


def test_service_rejects_openrouter_backend_without_key(db_session) -> None:
    card = create_card(
        db_session,
        title="OpenRouter missing key",
        category=KnowledgeCategory.PROJECT_EXPLANATION,
    )
    service = AnswerArenaService(
        KnowledgeCardRepository(db_session),
        settings=Settings(ai_score_backend="openrouter", openrouter_api_key=None),
    )

    with pytest.raises(AiScoringUnavailableError) as exc:
        service.score_answer(
            card_id=card.id,
            mode="ai",
            user_answer="This answer is long enough and structured for scoring.",
        )

    assert str(exc.value) == "OpenRouter API key is not configured."


def test_ai_score_payload_parser_defaults_missing_dimensions() -> None:
    result = parse_ai_score_payload(
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

    assert result.dimension_scores["direct_answer"] == 7
    assert result.dimension_scores["structure"] == 0


def test_ai_score_payload_parser_accepts_coaching_fields() -> None:
    payload = {
        "total_score": 90,
        "dimension_scores": {
            dimension: 8 for dimension in ANSWER_SCORE_DIMENSIONS
        },
        "strengths": ["结构清晰"],
        "problems": ["缺少项目落点"],
        "risk_expressions": [],
        "suggestions": ["补一个接口自动化例子"],
        "optimized_answer_30s": "30 秒旧字段答案",
        "memory_labels": ["项目表达"],
        "missing_points": ["缺少具体例子"],
        "complete_answer": "完整参考答案：先给结论，再讲接口自动化链路和风险边界。",
        "concrete_examples": [
            "pytest 示例：\nassert response.status_code == 200"
        ],
        "interview_answer_60s": "一分钟口述版：我会先说结论，再给例子。",
        "interview_answer_30s": "三十秒精简版：结论、例子、边界。",
        "follow_up_questions": ["你怎么做 SQL 断言？"],
        "follow_up_qas": [
            "Q：你怎么做 SQL 断言？\nA：我会用唯一业务编号查库，核对状态和关键字段。"
        ],
        "next_practice_step": "下次用 login -> db assert 讲一遍。",
    }

    result = parse_ai_score_payload(payload, provider="openrouter")

    assert result.provider == "openrouter"
    assert result.missing_points == ["缺少具体例子"]
    assert result.complete_answer.startswith("完整参考答案")
    assert "assert response.status_code == 200" in result.concrete_examples[0]
    assert result.interview_answer_60s.startswith("一分钟口述版")
    assert result.interview_answer_30s.startswith("三十秒精简版")
    assert result.follow_up_questions == ["你怎么做 SQL 断言？"]
    assert result.follow_up_qas[0].startswith("Q：你怎么做 SQL 断言")
    assert result.next_practice_step == "下次用 login -> db assert 讲一遍。"


def test_ai_score_payload_parser_defaults_missing_coaching_fields() -> None:
    result = parse_ai_score_payload(
        {
            "total_score": 80,
            "dimension_scores": {
                dimension: 7 for dimension in ANSWER_SCORE_DIMENSIONS
            },
            "strengths": [],
            "problems": [],
            "risk_expressions": [],
            "suggestions": [],
            "optimized_answer_30s": "fallback answer",
            "memory_labels": [],
        },
        provider="openai",
    )

    assert result.missing_points == []
    assert result.complete_answer == ""
    assert result.concrete_examples == []
    assert result.interview_answer_60s == ""
    assert result.interview_answer_30s == ""
    assert result.follow_up_questions == []
    assert result.follow_up_qas == []
    assert result.next_practice_step == ""


def test_ai_score_payload_parser_coerces_loose_list_and_score_fields() -> None:
    result = parse_ai_score_payload(
        {
            "total_score": "82",
            "dimension_scores": {
                "direct_answer": "8",
                "structure": "bad",
                "real_example": 9.3,
            },
            "strengths": "结构清晰",
            "problems": {"text": "缺少项目落点"},
            "risk_expressions": None,
            "suggestions": "补一个具体例子",
            "optimized_answer_30s": ["先说结论", "再说例子"],
            "memory_labels": {"value": ["项目表达", 123]},
            "missing_points": {"value": "缺少 SQL 断言"},
            "complete_answer": {"content": "完整答案内容"},
            "concrete_examples": [
                {"text": "assert response.status_code == 200"},
                {"description": "select status from users;"},
            ],
            "follow_up_questions": [{"question": "怎么定位失败？"}],
            "follow_up_qas": "Q：怎么定位失败？\nA：先复现，再看接口、日志和数据库。",
        },
        provider="openrouter",
    )

    assert result.total_score == 82
    assert result.dimension_scores["direct_answer"] == 8
    assert result.dimension_scores["structure"] == 0
    assert result.dimension_scores["real_example"] == 9
    assert result.strengths == ["结构清晰"]
    assert result.problems == ["缺少项目落点"]
    assert result.risk_expressions == []
    assert result.suggestions == ["补一个具体例子"]
    assert result.optimized_answer_30s == "先说结论\n再说例子"
    assert result.memory_labels == ["项目表达", "123"]
    assert result.missing_points == ["缺少 SQL 断言"]
    assert result.complete_answer == "完整答案内容"
    assert result.concrete_examples == [
        "assert response.status_code == 200",
        "select status from users;",
    ]
    assert result.follow_up_questions == ["Q：怎么定位失败？"]
    assert result.follow_up_qas == ["Q：怎么定位失败？\nA：先复现，再看接口、日志和数据库。"]


def test_ai_score_payload_parser_coerces_list_dict_follow_up_qas() -> None:
    result = parse_ai_score_payload(
        {
            "total_score": 75,
            "dimension_scores": {},
            "strengths": [{"text": "有结论"}, {"value": True}],
            "problems": [{"content": "例子不足"}],
            "risk_expressions": [],
            "suggestions": [],
            "optimized_answer_30s": {"answer": "三十秒回答"},
            "memory_labels": [],
            "follow_up_qas": [
                {"question": "为什么用 CSS Selector？", "answer": "因为稳定属性下写法更简洁。"},
                {"q": "XPath 何时更适合？", "a": "需要文本或兄弟节点定位时更适合。"},
            ],
        },
        provider="openai",
    )

    assert result.strengths == ["有结论", "True"]
    assert result.problems == ["例子不足"]
    assert result.optimized_answer_30s == "A：三十秒回答"
    assert result.follow_up_qas == [
        "Q：为什么用 CSS Selector？\nA：因为稳定属性下写法更简洁。",
        "Q：XPath 何时更适合？\nA：需要文本或兄弟节点定位时更适合。",
    ]


def test_openai_prompt_requires_example_first_coaching_by_topic(db_session) -> None:
    provider = OpenAIAnswerScoreProvider.__new__(OpenAIAnswerScoreProvider)
    python_card = create_card(
        db_session,
        title="Python fixture 怎么写？",
        category=KnowledgeCategory.PYTHON,
    )
    ui_card = create_card(
        db_session,
        title="UI 自动化元素怎么定位？",
        category=KnowledgeCategory.SELENIUM,
    )
    project_card = create_card(
        db_session,
        title="介绍服务端接口自动化项目",
        category=KnowledgeCategory.PROJECT_EXPLANATION,
    )
    hr_card = create_card(
        db_session,
        title="为什么从功能测试转测试开发？",
        category=KnowledgeCategory.HR_INTERVIEW,
    )

    python_prompt = provider._build_prompt(python_card, "answer")
    ui_prompt = provider._build_prompt(ui_card, "answer")
    project_prompt = provider._build_prompt(project_card, "answer")
    hr_prompt = provider._build_prompt(hr_card, "answer")

    assert "必须给 Python 代码例子" in python_prompt
    assert "CSS Selector / XPath 示例" in ui_prompt
    assert "真实项目表达模板" in project_prompt
    assert "STAR 结构" in hr_prompt
    assert "complete_answer" in project_prompt
    assert "interview_answer_60s" in project_prompt
    assert "follow_up_qas" in project_prompt
    assert "exactly 3" in project_prompt
    assert "next_practice_step" in project_prompt


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
