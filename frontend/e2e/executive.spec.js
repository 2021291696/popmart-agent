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

    // 显式等待 agent 卡片渲染（不吞失败）
    await expect(page.locator('.agent-card')).toHaveCount(2, { timeout: 5000 })

    // 检查至少有 2 个 agent 名称出现
    const content = await page.content()
    expect(content).toContain('ip_intelligence')
    expect(content).toContain('consumer_insights')
  })

  test('显示数据更新时间', async ({ page }) => {
    await page.goto('/executive')

    // 等待看板渲染完成后校验 footer 元数据
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
})
