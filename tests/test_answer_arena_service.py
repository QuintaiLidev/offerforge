from __future__ import annotations

from app.models.enums import KnowledgeCategory
from app.repositories import KnowledgeCardRepository
from app.schemas.knowledge_card import KnowledgeCardCreate
from app.services.answer_arena import AnswerArenaService


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
