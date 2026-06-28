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

    .schedule-info {
      display: grid;
      gap: 7px;
      padding: 12px;
      border-radius: 8px;
      background: #f7faf8;
      color: var(--text);
      font-size: 0.92rem;
    }

    .schedule-row {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      border-bottom: 1px solid #e7ece9;
      padding-bottom: 6px;
    }

    .schedule-row:last-child {
      border-bottom: 0;
      padding-bottom: 0;
    }

    .schedule-row strong {
      flex: 0 0 auto;
      color: var(--muted);
      font-weight: 700;
    }

    .schedule-row span {
      min-width: 0;
      text-align: right;
      word-break: break-word;
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

    .done-section {
      margin-top: 18px;
      padding: 16px;
    }

    .done-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 12px;
    }

    .done-header h2 {
      font-size: 1.08rem;
      line-height: 1.2;
    }

    .done-loading {
      color: var(--muted);
      font-size: 0.9rem;
    }

    .done-list {
      display: grid;
      gap: 12px;
    }

    .done-item {
      padding: 13px;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: #fbfcfd;
    }

    .done-title {
      margin-bottom: 8px;
      font-size: 1rem;
      line-height: 1.35;
    }

    .done-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-bottom: 10px;
    }

    .done-toggle {
      width: 100%;
      min-height: 42px;
      border: 0;
      border-radius: 8px;
      background: #e7eee9;
      color: var(--accent-strong);
      font: inherit;
      font-weight: 700;
      cursor: pointer;
      touch-action: manipulation;
    }

    .done-detail {
      display: none;
      margin-top: 10px;
      padding: 12px;
      border-radius: 8px;
      background: #f3f7f5;
    }

    .done-detail.visible {
      display: block;
    }

    .done-block + .done-block {
      margin-top: 10px;
    }

    .done-block strong {
      display: block;
      margin-bottom: 4px;
      color: var(--muted);
      font-size: 0.9rem;
    }

    .done-block p {
      white-space: pre-wrap;
      word-break: break-word;
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
        <h2>调度信息</h2>
        <div id="scheduleInfo" class="schedule-info"></div>
      </div>

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

    <section id="doneTodayPanel" class="panel done-section" aria-live="polite">
      <div class="done-header">
        <h2>今天已练习</h2>
        <span id="doneLoadingText" class="done-loading">加载中...</span>
      </div>
      <div id="doneEmptyState" class="empty hidden">今天还没有已练习卡片</div>
      <div id="doneList" class="done-list"></div>
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
      scheduleInfo: document.querySelector("#scheduleInfo"),
      cardTitle: document.querySelector("#cardTitle"),
      questionText: document.querySelector("#questionText"),
      showAnswerButton: document.querySelector("#showAnswerButton"),
      answerText: document.querySelector("#answerText"),
      answerInput: document.querySelector("#answerInput"),
      ratingButtons: Array.from(document.querySelectorAll("[data-rating]")),
      doneLoadingText: document.querySelector("#doneLoadingText"),
      doneEmptyState: document.querySelector("#doneEmptyState"),
      doneList: document.querySelector("#doneList"),
    };

    function setText(element, value) {
      element.textContent = value || "";
    }

    function formatValue(value) {
      return String(value || "").replace(/_/g, " ");
    }

    function formatDateTime(value) {
      if (!value) {
        return "暂无";
      }
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) {
        return "暂无";
      }
      return date.toLocaleString();
    }

    function formatOptionalDateTime(value) {
      const formatted = formatDateTime(value);
      return formatted === "暂无" ? "" : formatted;
    }

    const masteryLabels = {
      new: "新题",
      learning: "学习中",
      familiar: "熟悉中",
      reviewing: "巩固中",
      mastered: "已掌握",
    };

    const ratingLabels = {
      dont_know: "完全不会",
      with_hint: "看提示才会",
      correct_slow: "答对但慢",
      correct_explain: "能讲清楚",
      transfer: "能迁移应用",
    };

    function formatMappedValue(value, labels) {
      if (!value) {
        return "暂无";
      }
      return labels[value] || formatValue(value);
    }

    function formatCount(value) {
      if (value === 0) {
        return "0";
      }
      if (value === null || value === undefined || value === "") {
        return "暂无";
      }
      return String(value);
    }

    function createScheduleRow(label, value) {
      const row = document.createElement("div");
      row.className = "schedule-row";

      const title = document.createElement("strong");
      title.textContent = label;

      const content = document.createElement("span");
      content.textContent = value || "暂无";

      row.append(title, content);
      return row;
    }

    function fillScheduleInfo(container, card, latestAttempt = null) {
      const rows = [];
      if (latestAttempt) {
        rows.push(
          createScheduleRow(
            "本次评价",
            formatMappedValue(latestAttempt.rating, ratingLabels)
          )
        );
      }

      rows.push(
        createScheduleRow("掌握状态", formatMappedValue(card.mastery_level, masteryLabels)),
        createScheduleRow("连续正确", formatCount(card.consecutive_correct_count)),
        createScheduleRow("错误次数", formatCount(card.total_error_count)),
        createScheduleRow("上次练习", formatDateTime(card.last_practiced_at)),
        createScheduleRow("下次复习", formatDateTime(card.next_review_at))
      );
      container.replaceChildren(...rows);
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

    async function loadDoneToday() {
      elements.doneLoadingText.textContent = "加载中...";
      elements.doneEmptyState.classList.add("hidden");
      elements.doneList.replaceChildren();

      try {
        const doneToday = await fetchJson("/api/v1/reviews/done-today?limit=20");
        if (!doneToday.items.length) {
          elements.doneEmptyState.classList.remove("hidden");
          return;
        }

        doneToday.items.forEach((item) => {
          elements.doneList.appendChild(renderDoneItem(item));
        });
      } catch (error) {
        showError(`已练习加载失败：${error.message}`);
      } finally {
        elements.doneLoadingText.textContent = "";
      }
    }

    function createDoneBlock(label, text) {
      const block = document.createElement("div");
      block.className = "done-block";

      const title = document.createElement("strong");
      title.textContent = label;

      const content = document.createElement("p");
      content.textContent = text || "";

      block.append(title, content);
      return block;
    }

    function renderDoneItem(item) {
      const card = item.card;
      const attempt = item.latest_attempt;
      const wrapper = document.createElement("article");
      wrapper.className = "done-item";

      const title = document.createElement("h3");
      title.className = "done-title";
      title.textContent = card.title;

      const meta = document.createElement("div");
      meta.className = "done-meta";
      [
        card.category,
        card.difficulty,
        formatMappedValue(attempt.rating, ratingLabels),
        formatOptionalDateTime(attempt.created_at),
      ]
        .filter(Boolean)
        .forEach((value) => {
          const chip = document.createElement("span");
          chip.className = "chip";
          chip.textContent = formatValue(value);
          meta.appendChild(chip);
        });

      const toggle = document.createElement("button");
      toggle.className = "done-toggle";
      toggle.type = "button";
      toggle.textContent = "查看答案";

      const detail = document.createElement("div");
      detail.className = "done-detail";
      const scheduleBlock = document.createElement("div");
      scheduleBlock.className = "done-block";
      const scheduleTitle = document.createElement("strong");
      scheduleTitle.textContent = "调度信息";
      const scheduleInfo = document.createElement("div");
      scheduleInfo.className = "schedule-info";
      fillScheduleInfo(scheduleInfo, card, attempt);
      scheduleBlock.append(scheduleTitle, scheduleInfo);

      detail.append(
        scheduleBlock,
        createDoneBlock("题目", card.question),
        createDoneBlock("参考答案", card.reference_answer)
      );
      if (attempt.user_answer) {
        detail.appendChild(createDoneBlock("我的上次回答", attempt.user_answer));
      }

      toggle.addEventListener("click", () => {
        const visible = detail.classList.toggle("visible");
        toggle.textContent = visible ? "收起答案" : "查看答案";
      });

      wrapper.append(title, meta, toggle, detail);
      return wrapper;
    }

    function renderCard(card) {
      state.currentCard = card;
      state.cardStartedAt = Date.now();

      setText(elements.categoryText, formatValue(card.category));
      setText(elements.difficultyText, formatValue(card.difficulty));
      setText(elements.masteryText, formatMappedValue(card.mastery_level, masteryLabels));
      setText(elements.cardTitle, card.title);
      setText(elements.questionText, card.question);
      setText(elements.answerText, card.reference_answer);
      fillScheduleInfo(elements.scheduleInfo, card);
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
        await Promise.all([loadToday(), loadDoneToday()]);
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
    loadDoneToday();
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
