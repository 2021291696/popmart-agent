// 历史数据页 e2e
import { test, expect } from './fixtures.js'

test.describe('历史数据页', () => {
  test('显示历史分析记录列表', async ({ page }) => {
    await page.route('**/api/history', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          count: 2,
          items: [
            {
              query: '泡泡玛特市场表现如何？',
              saved_at: '2026-07-14 12:00',
              total_agents: 2,
              elapsed_seconds: 45.2,
              snippet: '核心结论：增长强劲',
              recommended_page: 'executive',
            },
            {
              query: 'LABUBU 为什么火？',
              saved_at: '2026-07-14 11:00',
              total_agents: 1,
              elapsed_seconds: 30.0,
              snippet: 'LABUBU 热度上升',
              recommended_page: 'supply',
            },
          ],
        }),
      })
    })

    await page.goto('/history')
    await expect(page.locator('h1, h2').first()).toContainText('历史数据')

    const content = await page.content()
    expect(content).toContain('泡泡玛特市场表现如何？')
    expect(content).toContain('LABUBU 为什么火？')
    expect(content).toContain('查看老板早会')
    expect(content).toContain('查看备货分析')
  })
})
