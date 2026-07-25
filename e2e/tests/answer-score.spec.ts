import { expect, test } from '@playwright/test';

test('规则评分会提交当前回答并展示评分结果', async ({ page }) => {
  const userAnswer =
    '我会先确认测试目标和业务风险，再准备独立测试数据，通过接口断言和数据库校验验证关键业务结果。';

  await page.route('**/api/v1/reviews/today?limit=10', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      json: {
        mode: 'due',
        items: [
          {
            id: 101,
            title: '如何设计可靠的接口自动化测试？',
            category: 'http_api_testing',
            difficulty: 'medium',
            mastery_level: 'learning',
            next_review_at: '2026-07-25T08:00:00Z',
          },
        ],
      },
    });
  });

  await page.route('**/api/v1/cards/101', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      json: {
        id: 101,
        title: '如何设计可靠的接口自动化测试？',
        category: 'http_api_testing',
        difficulty: 'medium',
        question_type: 'subjective',
        core_knowledge: '接口断言、数据隔离、数据库校验',
        question: '请说明你会如何设计一套可靠的接口自动化测试。',
        reference_answer:
          '先确认业务风险，再分层设计请求、断言、测试数据和数据库校验。',
        scoring_rules: {},
        tags: ['api', 'automation'],
        source_reference: 'playwright-e2e',
        is_active: true,
        mastery_level: 'learning',
        consecutive_correct_count: 1,
        total_error_count: 0,
        last_practiced_at: '2026-07-24T08:00:00Z',
        next_review_at: '2026-07-25T08:00:00Z',
      },
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

  await page.route('**/api/v1/answer-arena/score', async (route) => {
    expect(route.request().method()).toBe('POST');
    const requestBody = route.request().postDataJSON();
    expect(requestBody.card_id).toBe(101);
    expect(requestBody.mode).toBe('rule');
    expect(requestBody.user_answer).toBe(userAnswer);

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      json: {
        total_score: 88,
        provider: 'rule',
        dimension_scores: {
          direct_answer: 9,
          structure: 8,
          real_example: 8,
          job_match: 9,
          boundary: 9,
          professional_expression: 8,
          risk_control: 9,
        },
        strengths: ['回答包含测试目标、业务风险和数据校验。'],
        problems: [],
        risk_expressions: [],
        suggestions: ['补充失败定位和持续集成策略。'],
        optimized_answer_30s: '先确认风险，再分层设计请求、数据和断言。',
        memory_labels: ['风险', '数据', '断言'],
      },
    });
  });

  await page.goto('/app');

  await expect(
    page.getByRole('heading', {
      level: 2,
      name: '如何设计可靠的接口自动化测试？',
    }),
  ).toBeVisible();
  await expect(
    page.getByText('请说明你会如何设计一套可靠的接口自动化测试。'),
  ).toBeVisible();

  await page
    .getByPlaceholder('先写下或粘贴你的回答，再点击答题评分')
    .fill(userAnswer);
  await page.getByRole('button', { name: '规则评分' }).click();

  await expect(page.getByText('总分：88/100')).toBeVisible();
  await expect(page.getByText('provider: rule')).toBeVisible();
  await expect(
    page.getByText('回答包含测试目标、业务风险和数据校验。'),
  ).toBeVisible();
});
