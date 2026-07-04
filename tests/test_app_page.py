from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.main import create_app

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def make_client() -> AsyncIterator[httpx.AsyncClient]:
    application = create_app()
    transport = httpx.ASGITransport(app=application)
    async with application.router.lifespan_context(application):
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            yield client


async def test_app_page_auth_disabled_returns_mobile_review_page(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    monkeypatch.delenv("OFFERFORGE_AUTH_ENABLED", raising=False)
    monkeypatch.delenv("OFFERFORGE_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("OFFERFORGE_AUTH_PASSWORD", raising=False)
    get_settings.cache_clear()

    async for client in make_client():
        response = await client.get("/app")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "OfferForge" in response.text
    assert "<header>\n      <h1>OfferForge</h1>\n    </header>" in response.text
    header_body = response.text.split("<header>", 1)[1].split("</header>", 1)[0]
    assert "<p>今日复习</p>" not in header_body
    assert "练习历史" in response.text
    assert "review-section-title" in response.text
    assert "historyList" in response.text
    assert "展开历史" in response.text
    assert "我的回答" in response.text
    assert "scoreCurrentAnswer" in response.text
    assert "规则评分" in response.text
    assert "aiScoreAnswerButton" in response.text
    assert "AI快评" in response.text
    assert "deepScoreAnswerButton" in response.text
    assert "深度教练" in response.text
    assert 'scoreCurrentAnswer("rule")' in response.text
    assert 'scoreCurrentAnswer("ai_quick")' in response.text
    assert 'scoreCurrentAnswer("ai_deep")' in response.text
    assert 'addEventListener("click", scoreCurrentAnswer)' not in response.text
    assert "请至少输入 30 字回答后再评分" in response.text
    assert "AbortController" in response.text
    assert "timeoutMs" in response.text
    assert "90000" in response.text
    assert "30000" in response.text
    assert "AI快评中，预计 10-30 秒..." in response.text
    assert "深度教练中，完整答案可能需要 30-90 秒..." in response.text
    assert "AI快评超时：模型响应较慢，请稍后重试或改用规则评分。" in response.text
    assert "深度教练超时：完整答案生成较慢，请稍后重试或换稳定网络。" in response.text
    assert "AI快评请求失败：网络连接中断或服务暂时不可用，请稍后重试。" in response.text
    assert "深度教练请求失败：网络连接中断或服务暂时不可用，请稍后重试。" in response.text
    assert "getScoreRequestMode" in response.text
    assert "getScoreTimeoutMs" in response.text
    assert "formatScoreFailureMessage" in response.text
    assert "Load failed" in response.text
    assert "TypeError" in response.text
    assert "request timed out after" in response.text
    assert "window.clearTimeout(timeoutId)" in response.text
    assert "setLoading(false)" in response.text
    assert "mode: requestMode" in response.text
    assert "provider:" in response.text
    assert "你这次回答缺什么" in response.text
    assert "完整参考答案" in response.text
    assert "具体例子" in response.text
    assert "60秒面试口述版" in response.text
    assert "30秒精简版" in response.text
    assert "面试官可能追问" in response.text
    assert "面试官追问与简短回答" in response.text
    assert "下一步练习建议" in response.text
    assert "score-example-pre" in response.text
    assert "createOptionalScoreBlock" in response.text
    assert "interview_answer_30s" in response.text
    assert "follow_up_qas" in response.text
    assert "optimized_answer_30s" in response.text
    assert "/api/v1/answer-arena/score" in response.text
    assert "renderScoreResult" in response.text
    assert "编辑卡片" in response.text
    assert "edit-card-button" in response.text
    assert "card-edit-form" in response.text
    assert "createCardEditForm" in response.text
    assert "parseTagsInput" in response.text
    assert "reference_answer" in response.text
    assert "今日复习" in response.text
    assert "今日已练" in response.text
    assert "历史记录" in response.text
    assert "今天还没有已练习卡片" in response.text
    assert "tab-bar" in response.text
    assert 'data-tab="today"' in response.text
    assert 'data-tab="done"' in response.text
    assert 'data-tab="history"' in response.text
    assert 'class="tab-button active" type="button" data-tab="today"' in response.text
    assert 'aria-selected="true">今日复习' in response.text
    assert 'id="todayReviewPanel"' in response.text
    assert 'data-tab-panel="today"' in response.text
    assert 'id="doneTodayPanel"' in response.text
    assert 'data-tab-panel="done"' in response.text
    assert 'id="historyPanel"' in response.text
    assert 'data-tab-panel="history"' in response.text
    assert 'activeTab: "today"' in response.text
    assert "function setActiveTab(tabName)" in response.text
    assert "let successMessageTimer = null" in response.text
    assert "function showSuccess(message, durationMs = 1800)" in response.text
    assert "successMessageTimer = window.setTimeout(() =>" in response.text
    assert "function clearSuccess()" in response.text
    assert "window.clearTimeout(successMessageTimer)" in response.text
    assert "successMessageTimer = null" in response.text
    assert 'elements.todayReviewPanel.classList.toggle("hidden", tabName !== "today")' in response.text
    assert 'elements.doneTodayPanel.classList.toggle("hidden", tabName !== "done")' in response.text
    assert 'elements.historyPanel.classList.toggle("hidden", tabName !== "history")' in response.text
    assert 'button.addEventListener("click", () => setActiveTab(button.dataset.tab))' in response.text
    assert 'setActiveTab("today")' in response.text
    set_active_tab_body = response.text.split("function setActiveTab(tabName)", 1)[1].split(
        "async function fetchJson",
        1,
    )[0]
    assert "answerInput.value" not in set_active_tab_body
    assert 'if (tabName !== "today")' in set_active_tab_body
    assert "clearSuccess();" in set_active_tab_body
    assert "查看答案" in response.text
    assert "答案内容" in response.text
    assert "调度信息" in response.text
    assert "掌握状态" in response.text
    assert "连续正确" in response.text
    assert "错误次数" in response.text
    assert "上次练习" in response.text
    assert "下次复习" in response.text
    assert "本次评价" in response.text
    assert "mastery_level" in response.text
    assert "next_review_at" in response.text
    assert "consecutive_correct_count" in response.text
    assert "total_error_count" in response.text
    assert "last_practiced_at" in response.text
    assert "/api/v1/reviews/today" in response.text
    assert "/api/v1/reviews/done-today" in response.text
    assert "/api/v1/reviews/history?limit=50" in response.text
    assert "/api/v1/cards/${card.id}" in response.text
    assert 'method: "PATCH"' in response.text
    assert "/api/v1/practice-attempts" in response.text
    assert "request failed" in response.text
    assert "setButtonsDisabled(true, rating)" in response.text
    assert "scoreCurrentAnswer" in response.text
    assert "dataset.originalText" in response.text
    assert "state.submitting" in response.text
    assert "loadHistory()" in response.text
    assert "Promise.all([loadToday(), loadDoneToday(), loadHistory()])" in response.text
    assert "answer_text" in response.text
    assert "dont_know" in response.text
    assert "with_hint" in response.text
    assert "correct_slow" in response.text
    assert "correct_explain" in response.text
    assert "transfer" in response.text


async def test_root_redirects_to_app(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    monkeypatch.delenv("OFFERFORGE_AUTH_ENABLED", raising=False)
    monkeypatch.delenv("OFFERFORGE_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("OFFERFORGE_AUTH_PASSWORD", raising=False)
    get_settings.cache_clear()

    async for client in make_client():
        response = await client.get("/")

    assert response.status_code == 307
    assert response.headers["location"] == "/app"


async def test_app_page_auth_enabled_protects_app_but_not_health(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    monkeypatch.setenv("OFFERFORGE_AUTH_ENABLED", "true")
    monkeypatch.setenv("OFFERFORGE_AUTH_USERNAME", "offerforge")
    monkeypatch.setenv("OFFERFORGE_AUTH_PASSWORD", "test-secret")
    get_settings.cache_clear()

    async for client in make_client():
        root = await client.get("/")
        health = await client.get("/api/v1/health")
        app_without_auth = await client.get("/app")
        app_with_auth = await client.get(
            "/app",
            auth=("offerforge", "test-secret"),
        )

    assert root.status_code == 307
    assert root.headers["location"] == "/app"
    assert health.status_code == 200
    assert app_without_auth.status_code == 401
    assert app_without_auth.headers["www-authenticate"] == "Basic"
    assert app_with_auth.status_code == 200
    assert "OfferForge" in app_with_auth.text


async def test_app_page_does_not_break_docs_and_openapi_auth(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    monkeypatch.setenv("OFFERFORGE_AUTH_ENABLED", "true")
    monkeypatch.setenv("OFFERFORGE_AUTH_USERNAME", "offerforge")
    monkeypatch.setenv("OFFERFORGE_AUTH_PASSWORD", "test-secret")
    get_settings.cache_clear()

    async for client in make_client():
        docs_without_auth = await client.get("/docs")
        openapi_without_auth = await client.get("/openapi.json")
        docs_with_auth = await client.get(
            "/docs",
            auth=("offerforge", "test-secret"),
        )
        openapi_with_auth = await client.get(
            "/openapi.json",
            auth=("offerforge", "test-secret"),
        )

    assert docs_without_auth.status_code == 401
    assert openapi_without_auth.status_code == 401
    assert docs_without_auth.headers["www-authenticate"] == "Basic"
    assert openapi_without_auth.headers["www-authenticate"] == "Basic"
    assert docs_with_auth.status_code == 200
    assert openapi_with_auth.status_code == 200
