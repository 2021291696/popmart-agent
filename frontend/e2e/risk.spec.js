// Risk 页面 e2e 测试 - 冲突检测与仲裁
import { test, expect, MOCK_RISK_NO_CONFLICT } from './fixtures.js'

test.describe('Risk 页面 - 冲突检测与仲裁', () => {
  test('页面加载显示标题', async ({ page }) => {
    await page.goto('/risk')
    await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 5000 })
  })

  test('有冲突时显示冲突警告横幅', async ({ page }) => {
    await page.goto('/risk')

    // mock 数据 has_conflict: true
    await expect(page.locator('.status-card.conflict')).toBeVisible({ timeout: 8000 })
    const content = await page.content()
    expect(content).toContain('检测到')
    expect(content).toContain('冲突')
  })

  test('显示冲突对比卡片（两个 agent）', async ({ page }) => {
    await page.goto('/risk')

    await expect(page.locator('.conflict-card')).toHaveCount(1, { timeout: 8000 })
    const content = await page.content()
    expect(content).toContain('consumer_insights')
    expect(content).toContain('anti_counterfeit')
    // 冲突 vs 图标
    expect(content).toMatch(/⚔️|vs/i)
  })

  test('显示冲突理由（LLM 判断）', async ({ page }) => {
    await page.goto('/risk')

    await expect(page.locator('.conflict-reason')).toBeVisible({ timeout: 8000 })
    const content = await page.content()
    expect(content).toContain('LLM 判断')
    expect(content).toContain('维度')
  })

  test('仲裁过程按真实 total_rounds 渲染轮次', async ({ page }) => {
    await page.goto('/risk')

    // mock total_rounds: 2 → Round 1 + Round 2
    await expect(page.locator('.round-item')).toHaveCount(2, { timeout: 8000 })
    const content = await page.content()
    expect(content).toContain('Round 1')
    expect(content).toContain('Round 2')
  })

  test('有冲突时不显示「结论一致」徽章，改显示仲裁调和说明', async ({ page }) => {
    await page.goto('/risk')

    await expect(page.locator('.verification-row')).toBeVisible({ timeout: 8000 })
    const content = await page.content()
    // has_conflict: true → 不应出现「数据一致性已验证」
    expect(content).not.toContain('数据一致性已验证')
    expect(content).toContain('轮仲裁调和')
    expect(content).toContain('来源可追溯')
  })

  test('无冲突时显示"无冲突"状态与一致性徽章', async ({ page }) => {
    // 重新 route risk API 返回无冲突版本
    await page.route(/\/api\/visualize\/risk/, (route) =>
      route.fulfill({ json: MOCK_RISK_NO_CONFLICT, status: 200 })
    )
    await page.goto('/risk')

    await expect(page.locator('.status-card.ok')).toBeVisible({ timeout: 8000 })
    const content = await page.content()
    expect(content).toContain('无冲突')
    expect(content).toContain('数据一致性已验证')
    expect(content).toContain('来源可追溯')
  })
})
