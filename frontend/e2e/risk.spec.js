// Risk 页面 e2e 测试 - 冲突检测与仲裁（数据源：GET /api/boards/risk）
import { test, expect, MOCK_BOARD_RISK, MOCK_BOARD_RISK_NO_CONFLICT, BOARD_404_BODY } from './fixtures.js'

test.describe('Risk 页面 - 冲突检测与仲裁', () => {
  test('页面加载显示标题', async ({ page }) => {
    await page.goto('/risk')
    await expect(page.locator('h1').first()).toContainText('客诉应对')
  })

  test('有冲突时显示冲突警告横幅', async ({ page }) => {
    await page.goto('/risk')

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
    // conflicts 非空 → 不应出现「数据一致性已验证」
    expect(content).not.toContain('数据一致性已验证')
    expect(content).toContain('轮仲裁调和')
    expect(content).toContain('来源可追溯')
  })

  test('无冲突时显示"无冲突"状态与一致性徽章', async ({ page }) => {
    await page.route(/\/api\/boards\/risk$/, (route) =>
      route.fulfill({ json: MOCK_BOARD_RISK_NO_CONFLICT, status: 200 })
    )
    await page.goto('/risk')

    await expect(page.locator('.status-card.ok')).toBeVisible({ timeout: 8000 })
    const content = await page.content()
    expect(content).toContain('无冲突')
    expect(content).toContain('数据一致性已验证')
    expect(content).toContain('来源可追溯')
  })

  test('无缓存（404）→ 空态引导「点击刷新分析生成」', async ({ page }) => {
    await page.route(/\/api\/boards\/risk$/, (route) =>
      route.fulfill({ status: 404, json: BOARD_404_BODY })
    )
    await page.goto('/risk')

    const empty = page.locator('.board-empty')
    await expect(empty).toBeVisible({ timeout: 8000 })
    await expect(empty).toContainText('该看板尚无分析结果')
    await expect(empty.locator('.board-empty-btn')).toContainText('点击刷新分析生成')
  })

  test('有 charts → 客诉情感画像渲染（环形 + 逐条强度）', async ({ page }) => {
    await page.goto('/risk')

    await expect(page.locator('.charts-section')).toBeVisible({ timeout: 8000 })
    // risk 只渲染 sentiment 两张卡（ip_mentions 为 null，无 IP 热度图）
    await expect(page.locator('.chart-card')).toHaveCount(2)
    await expect(page.locator('.recharts-responsive-container')).toHaveCount(2)
    const content = await page.content()
    expect(content).toContain('客诉情感画像')
    expect(content).toContain('情感倾向分布')
    expect(content).toContain('逐条情感强度')
  })

  test('无 charts → 图表区整块不存在（含标题）', async ({ page }) => {
    await page.route(/\/api\/boards\/risk$/, (route) =>
      route.fulfill({
        json: { ...MOCK_BOARD_RISK, charts: { agent_activity: [], ip_mentions: null, sentiment: null } },
        status: 200,
      })
    )
    await page.goto('/risk')

    await expect(page.locator('.status-card.conflict')).toBeVisible({ timeout: 8000 })
    await expect(page.locator('.charts-section')).toHaveCount(0)
    await expect(page.locator('.chart-card')).toHaveCount(0)
    // 原有区块不受影响
    await expect(page.locator('.conflict-card')).toHaveCount(1)
  })
})
