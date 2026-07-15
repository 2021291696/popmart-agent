// Supply 页面 e2e 测试 - ReAct 推理时间线（数据源：GET /api/boards/supply）
import { test, expect, BOARD_404_BODY } from './fixtures.js'

test.describe('Supply 页面 - ReAct 推理时间线', () => {
  test('页面加载显示标题', async ({ page }) => {
    await page.goto('/supply')
    await expect(page.locator('h1').first()).toContainText('备货分析')
  })

  test('显示 ReAct 时间线步骤（至少 3 步）', async ({ page }) => {
    await page.goto('/supply')

    const dots = page.locator('.timeline-dot')
    await expect(dots.first()).toBeVisible({ timeout: 8000 })
    const count = await dots.count()
    expect(count).toBeGreaterThanOrEqual(3)
  })

  test('时间线包含 Thought/Action/Observation 三要素', async ({ page }) => {
    await page.goto('/supply')

    await expect(page.locator('.timeline-item').first()).toBeVisible({ timeout: 8000 })
    const content = await page.content()
    expect(content).toContain('Thought')
    expect(content).toContain('Action')
    expect(content).toContain('Observation')
  })

  test('显示工具调用统计表格', async ({ page }) => {
    await page.goto('/supply')

    await expect(page.locator('.tools-card')).toBeVisible({ timeout: 8000 })
    const content = await page.content()
    expect(content).toContain('web_search')
    expect(content).toContain('sentiment_analyze')
    expect(content).toContain('trend_compare')
  })

  test('显示最终结论', async ({ page }) => {
    await page.goto('/supply')

    await expect(page.locator('.report-card')).toBeVisible({ timeout: 8000 })
    const content = await page.content()
    expect(content).toContain('稀缺性营销')
  })

  test('无缓存（404）→ 空态引导「点击刷新分析生成」', async ({ page }) => {
    await page.route(/\/api\/boards\/supply$/, (route) =>
      route.fulfill({ status: 404, json: BOARD_404_BODY })
    )
    await page.goto('/supply')

    const empty = page.locator('.board-empty')
    await expect(empty).toBeVisible({ timeout: 8000 })
    await expect(empty).toContainText('该看板尚无分析结果')
    await expect(empty.locator('.board-empty-btn')).toContainText('点击刷新分析生成')
  })
})
