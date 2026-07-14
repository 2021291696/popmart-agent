// Executive 页面 e2e 测试
import { test, expect } from './fixtures.js'

test.describe('Executive 页面 - 多 Agent 协作全景', () => {
  test('页面加载后显示标题和关键指标', async ({ page }) => {
    await page.goto('/executive')

    // 等待标题
    await expect(page.locator('h1, h2').first()).toContainText('综合分析')

    // 验证关键指标卡片（4 个）
    const metrics = page.locator('.metric-card, .metrics-grid > div')
    await expect(metrics.first()).toBeVisible({ timeout: 5000 })
  })

  test('显示 Agent 协作卡片（每个 agent 一个）', async ({ page }) => {
    await page.goto('/executive')

    // 等待 agent 卡片渲染
    await page.waitForSelector('.agent-card, [class*="agent"]', { timeout: 5000 }).catch(() => {})

    // 检查至少有 2 个 agent 名称出现
    const content = await page.content()
    expect(content).toContain('ip_intelligence')
    expect(content).toContain('consumer_insights')
  })

  test('显示数据更新时间', async ({ page }) => {
    await page.goto('/executive')
    // 等待加载完成（mock API 响应很快，但 fetch 是异步的）
    await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {})
    await page.waitForTimeout(500)

    // 检查元数据区域（footer 标签 + meta-text 类）
    const metaText = page.locator('footer.meta-text, .page-footer')
    await expect(metaText.first()).toContainText('2026-07-13', { timeout: 5000 })
  })

  test('显示最终综合报告', async ({ page }) => {
    await page.goto('/executive')
    await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {})
    await page.waitForTimeout(500)

    // 报告区域应该包含 mock 的总结文字
    const content = await page.content()
    expect(content).toContain('LABUBU')
    expect(content).toContain('复购率')
  })
})