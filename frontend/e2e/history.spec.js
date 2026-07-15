// 历史数据页 e2e
import { test, expect } from './fixtures.js'

test.describe('历史数据页', () => {
  test('显示历史分析记录列表', async ({ page }) => {
    // 使用 fixtures 默认的 /api/history mock（两条记录）
    await page.goto('/history')
    await expect(page.locator('h1, h2').first()).toContainText('历史数据')

    await expect(page.locator('.history-card')).toHaveCount(2, { timeout: 8000 })
    const content = await page.content()
    expect(content).toContain('泡泡玛特最近的市场表现如何？')
    expect(content).toContain('LABUBU 为什么能成为泡泡玛特的核心IP？')
    expect(content).toContain('查看老板早会')
    expect(content).toContain('查看备货分析')
  })
})
