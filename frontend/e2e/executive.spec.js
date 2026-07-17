// Executive 页面 e2e 测试（数据源：GET /api/boards/executive）
import { test, expect, mockJob, MOCK_JOB_ID, MOCK_BOARD_EXECUTIVE, BOARD_404_BODY } from './fixtures.js'

test.describe('Executive 页面 - 多 Agent 协作全景', () => {
  test('页面加载后显示标题和关键指标', async ({ page }) => {
    await page.goto('/executive')

    await expect(page.locator('h1').first()).toContainText('老板早会')

    // 验证关键指标卡片（4 个）
    const metrics = page.locator('.metric-card')
    await expect(metrics).toHaveCount(4, { timeout: 5000 })
  })

  test('显示 Agent 协作卡片（每个 agent 一个）', async ({ page }) => {
    await page.goto('/executive')

    await expect(page.locator('.agent-card')).toHaveCount(2, { timeout: 5000 })

    const content = await page.content()
    expect(content).toContain('ip_intelligence')
    expect(content).toContain('consumer_insights')
  })

  test('显示数据更新时间', async ({ page }) => {
    await page.goto('/executive')

    await expect(page.locator('.metric-card').first()).toBeVisible({ timeout: 5000 })
    const metaText = page.locator('footer.meta-text, .page-footer')
    await expect(metaText.first()).toContainText('2026-07-13', { timeout: 5000 })
  })

  test('显示最终综合报告', async ({ page }) => {
    await page.goto('/executive')

    await expect(page.locator('.report-card')).toBeVisible({ timeout: 5000 })
    const content = await page.content()
    expect(content).toContain('LABUBU')
    expect(content).toContain('复购率')
  })

  test('无缓存（404）→ 空态引导「点击刷新分析生成」', async ({ page }) => {
    await page.route(/\/api\/boards\/executive$/, (route) =>
      route.fulfill({ status: 404, json: BOARD_404_BODY })
    )
    await page.goto('/executive')

    const empty = page.locator('.board-empty')
    await expect(empty).toBeVisible({ timeout: 8000 })
    await expect(empty).toContainText('该看板尚无分析结果')
    await expect(empty.locator('.board-empty-btn')).toContainText('点击刷新分析生成')
  })

  test('点击「刷新分析」→ 创建 job 并跳转进度页', async ({ page }) => {
    // job 保持 running：进度页不会因 complete 跳走，稳定停留在 /progress/{id}
    await page.route(/\/api\/jobs\/[^/]+$/, (route) =>
      route.fulfill({ json: mockJob({ status: 'running', recommended_page: null }), status: 200 })
    )
    await page.goto('/executive')
    await expect(page.locator('.metric-card').first()).toBeVisible({ timeout: 5000 })

    await page.click('.board-refresh-btn')
    await expect(page).toHaveURL(new RegExp(`/progress/${MOCK_JOB_ID}`))
  })

  test('刷新冲突（409）→ 显示「该看板已有分析任务进行中」', async ({ page }) => {
    await page.route(/\/api\/boards\/executive\/refresh$/, (route) =>
      route.fulfill({ status: 409, json: { detail: '该看板已有分析任务进行中' } })
    )
    await page.goto('/executive')
    await expect(page.locator('.metric-card').first()).toBeVisible({ timeout: 5000 })

    await page.click('.board-refresh-btn')
    await expect(page.locator('.board-toolbar-error')).toContainText('该看板已有分析任务进行中')
  })

  test('有 charts → 数据速览图表渲染（含诚实标注 note）', async ({ page }) => {
    await page.goto('/executive')

    await expect(page.locator('.charts-section')).toBeVisible({ timeout: 8000 })
    await expect(page.locator('.chart-card')).toHaveCount(4)
    // recharts 真图表容器 + 四张卡标题
    await expect(page.locator('.recharts-responsive-container')).toHaveCount(4)
    const content = await page.content()
    expect(content).toContain('Agent 工作量对比')
    expect(content).toContain('IP 热度提及量')
    expect(content).toContain('情感倾向分布')
    expect(content).toContain('逐条情感强度')
    // 诚实标注 note 原文展示
    expect(content).toContain('非真实时序指数')
  })

  test('无 charts → 图表区整块不存在（含标题）', async ({ page }) => {
    await page.route(/\/api\/boards\/executive$/, (route) =>
      route.fulfill({
        json: { ...MOCK_BOARD_EXECUTIVE, charts: { agent_activity: [], ip_mentions: null, sentiment: null } },
        status: 200,
      })
    )
    await page.goto('/executive')

    await expect(page.locator('.metric-card').first()).toBeVisible({ timeout: 5000 })
    await expect(page.locator('.charts-section')).toHaveCount(0)
    await expect(page.locator('.chart-card')).toHaveCount(0)
    // 原有区块不受影响
    await expect(page.locator('.agent-card')).toHaveCount(2)
  })
})
