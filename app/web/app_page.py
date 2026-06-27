from __future__ import annotations

from fastapi import APIRouter, status
from starlette.responses import HTMLResponse

router: APIRouter = APIRouter(tags=["App"])

APP_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OfferForge</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f7f9;
      --surface: #ffffff;
      --text: #17202a;
      --muted: #5d6875;
      --border: #d9dee5;
      --accent: #1d6f5f;
      --accent-strong: #15584c;
      --danger-bg: #fff0f0;
      --danger: #9f2424;
      --success-bg: #edf8f1;
      --success: #176a3a;
      --shadow: 0 10px 30px rgba(18, 28, 45, 0.08);
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      font-size: 16px;
      line-height: 1.5;
    }

    main {
      width: min(100%, 520px);
      min-height: 100vh;
      margin: 0 auto;
      padding: 24px 18px 36px;
    }

    header {
      margin-bottom: 18px;
    }

    h1,
    h2,
    p {
      margin: 0;
    }

    h1 {
      font-size: 2rem;
      line-height: 1.1;
      letter-spacing: 0;
    }

    header p {
      margin-top: 6px;
      color: var(--muted);
      font-size: 1rem;
    }

    .status-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      min-height: 28px;
      margin-bottom: 14px;
      color: var(--muted);
      font-size: 0.95rem;
    }

    .mode {
      padding: 3px 10px;
      border: 1px solid var(--border);
      border-radius: 999px;
      background: var(--surface);
      color: var(--text);
      font-size: 0.9rem;
    }

    .panel {
      border: 1px solid var(--border);
      border-radius: 8px;
      background: var(--surface);
      box-shadow: var(--shadow);
    }

    .card {
      padding: 18px;
    }

    .meta {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 0 0 14px;
    }

    .chip {
      min-height: 28px;
      padding: 4px 9px;
      border-radius: 999px;
      background: #eef2f4;
      color: #34404c;
      font-size: 0.86rem;
    }

    .title {
      margin-bottom: 16px;
      font-size: 1.45rem;
      line-height: 1.2;
      letter-spacing: 0;
    }

    .section {
      margin-top: 16px;
      padding-top: 16px;
      border-top: 1px solid var(--border);
    }

    .section h2 {
      margin-bottom: 8px;
      color: var(--muted);
      font-size: 0.95rem;
      font-weight: 700;
    }

    .question,
    .answer {
      white-space: pre-wrap;
      word-break: break-word;
    }

    .answer {
      display: none;
      margin-top: 10px;
      padding: 13px;
      border-radius: 8px;
      background: #f3f7f5;
    }

    .answer.visible {
      display: block;
    }

    .answer-toggle,
    .rating-button {
      width: 100%;
      min-height: 48px;
      border: 0;
      border-radius: 8px;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
      touch-action: manipulation;
    }

    .answer-toggle {
      margin-top: 14px;
      background: #e7eee9;
      color: var(--accent-strong);
    }

    .answer-toggle:disabled,
    .rating-button:disabled {
      cursor: wait;
      opacity: 0.58;
    }

    .answer-input {
      width: 100%;
      min-height: 96px;
      resize: vertical;
      padding: 12px;
      border: 1px solid var(--border);
      border-radius: 8px;
      color: var(--text);
      font: inherit;
    }

    .rating-list {
      display: grid;
      gap: 10px;
      margin-top: 12px;
    }

    .rating-button {
      background: var(--accent);
      color: #ffffff;
      text-align: left;
      padding: 12px 14px;
    }

    .rating-button:active {
      transform: translateY(1px);
    }

    .notice,
    .empty,
    .error {
      padding: 14px;
      border-radius: 8px;
      margin-bottom: 14px;
    }

    .notice {
      display: none;
      background: var(--success-bg);
      color: var(--success);
    }

    .notice.visible {
      display: block;
    }

    .error {
      display: none;
      background: var(--danger-bg);
      color: var(--danger);
    }

    .error.visible {
      display: block;
    }

    .empty {
      color: var(--muted);
      text-align: center;
    }

    .hidden {
      display: none;
    }
  </style>
</head>
<body>
  <main>
    <header>
      <h1>OfferForge</h1>
      <p>今日复习</p>
    </header>

    <div class="status-row" aria-live="polite">
      <span id="loadingText">加载中...</span>
      <span id="modeText" class="mode hidden">mode: due</span>
    </div>

    <div id="successMessage" class="notice" role="status"></div>
    <div id="errorMessage" class="error" role="alert"></div>
    <section id="emptyState" class="panel empty hidden">今天没有需要复习的内容。</section>

    <section id="cardPanel" class="panel card hidden" aria-live="polite">
      <div class="meta">
        <span id="categoryText" class="chip"></span>
        <span id="difficultyText" class="chip"></span>
        <span id="masteryText" class="chip"></span>
      </div>

      <h2 id="cardTitle" class="title"></h2>

      <div class="section">
        <h2>题目</h2>
        <p id="questionText" class="question"></p>
      </div>

      <div class="section">
        <button id="showAnswerButton" class="answer-toggle" type="button">显示答案</button>
        <div id="answerText" class="answer"></div>
      </div>

      <div class="section">
        <h2>答题记录</h2>
        <textarea
          id="answerInput"
          class="answer-input"
          name="answer_text"
          autocomplete="off"
          placeholder="可选：记录你的回答"
        ></textarea>
      </div>

      <div class="section">
        <h2>评价</h2>
        <div class="rating-list" id="ratingButtons">
          <button class="rating-button" type="button" data-rating="dont_know">完全不会</button>
          <button class="rating-button" type="button" data-rating="with_hint">看提示才能完成</button>
          <button class="rating-button" type="button" data-rating="correct_slow">正确但较慢</button>
          <button class="rating-button" type="button" data-rating="correct_explain">正确且能解释</button>
          <button class="rating-button" type="button" data-rating="transfer">能迁移到新场景</button>
        </div>
      </div>
    </section>
  </main>

  <script>
    const state = {
      currentCard: null,
      cardStartedAt: null,
      submitting: false,
    };

    const elements = {
      loadingText: document.querySelector("#loadingText"),
      modeText: document.querySelector("#modeText"),
      successMessage: document.querySelector("#successMessage"),
      errorMessage: document.querySelector("#errorMessage"),
      emptyState: document.querySelector("#emptyState"),
      cardPanel: document.querySelector("#cardPanel"),
      categoryText: document.querySelector("#categoryText"),
      difficultyText: document.querySelector("#difficultyText"),
      masteryText: document.querySelector("#masteryText"),
      cardTitle: document.querySelector("#cardTitle"),
      questionText: document.querySelector("#questionText"),
      showAnswerButton: document.querySelector("#showAnswerButton"),
      answerText: document.querySelector("#answerText"),
      answerInput: document.querySelector("#answerInput"),
      ratingButtons: Array.from(document.querySelectorAll("[data-rating]")),
    };

    function setText(element, value) {
      element.textContent = value || "";
    }

    function formatValue(value) {
      return String(value || "").replace(/_/g, " ");
    }

    function showError(message) {
      setText(elements.errorMessage, message);
      elements.errorMessage.classList.add("visible");
    }

    function clearError() {
      setText(elements.errorMessage, "");
      elements.errorMessage.classList.remove("visible");
    }

    function showSuccess(message) {
      setText(elements.successMessage, message);
      elements.successMessage.classList.add("visible");
    }

    function clearSuccess() {
      setText(elements.successMessage, "");
      elements.successMessage.classList.remove("visible");
    }

    function setLoading(isLoading) {
      elements.loadingText.textContent = isLoading ? "加载中..." : "";
    }

    function setButtonsDisabled(disabled) {
      elements.showAnswerButton.disabled = disabled;
      elements.ratingButtons.forEach((button) => {
        button.disabled = disabled;
      });
    }

    async function fetchJson(url, options = {}) {
      const headers = {
        Accept: "application/json",
        ...(options.headers || {}),
      };
      const response = await fetch(url, {
        ...options,
        headers,
        credentials: "same-origin",
      });
      if (!response.ok) {
        let message = `${response.status} ${response.statusText}`;
        try {
          const data = await response.json();
          if (data.detail) {
            message = Array.isArray(data.detail)
              ? data.detail.map((item) => item.msg || String(item)).join("; ")
              : String(data.detail);
          }
        } catch (error) {
          // Keep the HTTP status message when the response body is not JSON.
        }
        throw new Error(message);
      }
      return response.json();
    }

    async function loadToday() {
      clearError();
      setLoading(true);
      elements.emptyState.classList.add("hidden");
      elements.cardPanel.classList.add("hidden");
      elements.modeText.classList.add("hidden");
      setButtonsDisabled(true);

      try {
        const today = await fetchJson("/api/v1/reviews/today?limit=10");
        elements.modeText.textContent = `mode: ${today.mode}`;
        elements.modeText.classList.remove("hidden");

        if (!today.items.length) {
          state.currentCard = null;
          state.cardStartedAt = null;
          elements.emptyState.classList.remove("hidden");
          return;
        }

        const summary = today.items[0];
        const detail = await fetchJson(`/api/v1/cards/${summary.id}`);
        renderCard(detail);
      } catch (error) {
        showError(`加载失败：${error.message}`);
      } finally {
        setLoading(false);
      }
    }

    function renderCard(card) {
      state.currentCard = card;
      state.cardStartedAt = Date.now();

      setText(elements.categoryText, formatValue(card.category));
      setText(elements.difficultyText, formatValue(card.difficulty));
      setText(elements.masteryText, formatValue(card.mastery_level));
      setText(elements.cardTitle, card.title);
      setText(elements.questionText, card.question);
      setText(elements.answerText, card.reference_answer);
      elements.answerInput.value = "";
      elements.answerText.classList.remove("visible");
      elements.showAnswerButton.textContent = "显示答案";
      elements.cardPanel.classList.remove("hidden");
      setButtonsDisabled(false);
    }

    function toggleAnswer() {
      const visible = elements.answerText.classList.toggle("visible");
      elements.showAnswerButton.textContent = visible ? "隐藏答案" : "显示答案";
    }

    async function submitRating(rating) {
      if (!state.currentCard || state.submitting) {
        return;
      }

      clearError();
      clearSuccess();
      state.submitting = true;
      setButtonsDisabled(true);

      const answerText = elements.answerInput.value.trim();
      const elapsedSeconds = Math.max(
        0,
        Math.round((Date.now() - state.cardStartedAt) / 1000)
      );

      try {
        await fetchJson("/api/v1/practice-attempts", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({
            knowledge_card_id: state.currentCard.id,
            rating,
            answer_text: answerText || null,
            user_answer: answerText || null,
            elapsed_seconds: elapsedSeconds,
          }),
        });
        await loadToday();
        showSuccess("提交成功");
      } catch (error) {
        showError(`提交失败：${error.message}`);
        setButtonsDisabled(false);
      } finally {
        state.submitting = false;
      }
    }

    elements.showAnswerButton.addEventListener("click", toggleAnswer);
    elements.ratingButtons.forEach((button) => {
      button.addEventListener("click", () => submitRating(button.dataset.rating));
    });

    loadToday();
  </script>
</body>
</html>
"""


@router.get(
    "/app",
    include_in_schema=False,
    response_class=HTMLResponse,
    status_code=status.HTTP_200_OK,
)
def review_app() -> HTMLResponse:
    return HTMLResponse(APP_HTML)
