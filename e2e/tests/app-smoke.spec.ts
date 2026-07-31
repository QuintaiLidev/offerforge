import { expect, test } from '@playwright/test';

test('SkillLoop主页面可以正常打开并切换复习Tab', async ({ page }) => {
  await page.goto('/app');

  await expect(page).toHaveTitle('SkillLoop');
  await expect(
    page.getByRole('heading', { level: 1, name: 'SkillLoop' }),
  ).toBeVisible();

  const todayTab = page.getByRole('button', { name: '今日复习' });
  const doneTodayTab = page.getByRole('button', { name: '今日已练' });
  const historyTab = page.getByRole('button', { name: '历史记录' });

  await expect(todayTab).toHaveAttribute('aria-selected', 'true');

  await doneTodayTab.click();
  await expect(doneTodayTab).toHaveAttribute('aria-selected', 'true');
  await expect(page.locator('#doneTodayPanel')).toBeVisible();

  await historyTab.click();
  await expect(historyTab).toHaveAttribute('aria-selected', 'true');
  await expect(page.locator('#historyPanel')).toBeVisible();
});
