// Risk 页面 e2e 测试 - 冲突检测与仲裁
import { test, expect } from './fixtures.js'

test.describe('Risk 页面 - 冲突检测与仲裁', () => {
  test('页面加载显示标题', async ({ page }) => {
    await page.goto('/risk')
    await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 5000 })
  })

  test('有冲突时显示冲突警告横幅', async ({ page }) => {
    await page.goto('/risk')
    await page.waitForTimeout(1000)

    const content = await page.content()
    // mock 数据 has_conflict: true
    expect(content).toContain('检测到')
    expect(content).toContain('冲突')
  })

  test('显示冲突对比卡片（两个 agent）', async ({ page }) => {
    await page.goto('/risk')
    await page.waitForTimeout(1000)

    const content = await page.content()
    expect(content).toContain('consumer_insights')
    expect(content).toContain('anti_counterfeit')
    // 冲突 vs 图标
    expect(content).toMatch(/⚔️|vs/)
  })

  test('显示冲突理由（LLM 判断）', async ({ page }) => {
    await page.goto('/risk')
    await page.waitForTimeout(1000)

    const content = await page.content()
    expect(content).toContain('LLM 判断')
    expect(content).toContain('维度')
  })

  test('显示仲裁过程（Round 1 + Round 2）', async ({ page }) => {
    await page.goto('/risk')
    await page.waitForTimeout(1000)

    const content = await page.content()
    expect(content).toContain('Round 1')
    expect(content).toContain('Round 2')
  })

  test('显示调和结论和验证徽章', async ({ page }) => {
    await page.goto('/risk')
    await page.waitForTimeout(1000)

    const content = await page.content()
    expect(content).toContain('调和结论')
    expect(content).toContain('数据一致性')
    expect(content).toContain('来源可追溯')
  })

  test('无冲突时显示"无冲突"状态', async ({ page }) => {
    // 重新 route risk API 返回无冲突版本
    await page.route('**/api/visualize/risk', (route) =>
      route.fulfill({
        json: {
          query: 'test',
          title: '消费者风险分析',
          generated_at: '2026-07-13',
          final_answer: '无冲突结论',
          total_rounds: 1,
          has_conflict: false,
          conflicts: [],
          agents: [],
        },
        status: 200,
      })
    )
    await page.goto('/risk')
    await page.waitForTimeout(1000)

    const content = await page.content()
    expect(content).toContain('无冲突')
  })
})