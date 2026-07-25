import { expect, test } from '@playwright/test';

test('提交练习评价时发送正确请求并展示成功结果', async ({ page }) => {
  const userAnswer =
    '我会先确认业务目标和核心风险，再准备独立测试数据，通过接口响应、数据库状态和日志验证完整结果。';
  const card = {
    id: 202,
    title: '如何验证接口提交后的业务结果？',
    category: 'http_api_testing',
    difficulty: 'medium',
    question_type: 'subjective',
    core_knowledge: '接口断言、数据库校验、日志定位',
    question: '接口返回成功后，你会怎样确认业务结果真正正确？',
    reference_answer:
      '除了检查响应，还要核对数据库状态、关联流水、日志和必要的下游结果。',
    scoring_rules: {},
    tags: ['api', 'database'],
    source_reference: 'playwright-e2e',
    is_active: true,
    mastery_level: 'learning',
    consecutive_correct_count: 1,
    total_error_count: 0,
    last_practiced_at: '2026-07-24T08:00:00Z',
    next_review_at: '2026-07-25T08:00:00Z',
  };

  await page.route('**/api/v1/reviews/today?limit=10', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      json: {
        mode: 'due',
        items: [
          {
            id: card.id,
            title: card.title,
            category: card.category,
            difficulty: card.difficulty,
            mastery_level: card.mastery_level,
            next_review_at: card.next_review_at,
          },
        ],
      },
    });
  });

  await page.route('**/api/v1/cards/202', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      json: card,
    });
  });

  await page.route(
    '**/api/v1/reviews/done-today?limit=20',
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        json: { items: [] },
      });
    },
  );

  await page.route('**/api/v1/reviews/history?limit=50', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      json: { items: [] },
    });
  });

  let practiceRequestCount = 0;
  let releasePracticeRequest!: () => void;
  const practiceRequestGate = new Promise<void>((resolve) => {
    releasePracticeRequest = resolve;
  });

  await page.route('**/api/v1/practice-attempts', async (route) => {
    practiceRequestCount += 1;
    expect(route.request().method()).toBe('POST');

    const requestBody = route.request().postDataJSON();
    expect(requestBody.knowledge_card_id).toBe(202);
    expect(requestBody.rating).toBe('correct_explain');
    expect(requestBody.answer_text).toBe(userAnswer);
    expect(requestBody.user_answer).toBe(userAnswer);
    expect(typeof requestBody.elapsed_seconds).toBe('number');
    expect(requestBody.elapsed_seconds).toBeGreaterThanOrEqual(0);

    await practiceRequestGate;
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      json: {
        attempt: {
          id: 303,
          knowledge_card_id: 202,
          rating: 'correct_explain',
          is_correct: true,
          used_hint: false,
          user_answer: userAnswer,
          elapsed_seconds: requestBody.elapsed_seconds,
          error_summary: null,
          feedback: null,
          scheduled_next_review_at: '2026-07-28T08:00:00Z',
          created_at: '2026-07-25T08:00:00Z',
        },
        card,
      },
    });
  });

  await page.goto('/app');

  await page
    .getByPlaceholder('先写下或粘贴你的回答，再点击答题评分')
    .fill(userAnswer);

  const submitButton = page.locator(
    'button[data-rating="correct_explain"]',
  );
  await page.getByRole('button', { name: '正确且能解释' }).click();
  await expect.poll(() => practiceRequestCount).toBe(1);
  await expect(submitButton).toBeDisabled();

  await submitButton.evaluate((button: HTMLButtonElement) => button.click());
  expect(practiceRequestCount).toBe(1);

  releasePracticeRequest();

  await expect(page.getByText('提交成功')).toBeVisible();
  expect(practiceRequestCount).toBe(1);
});
