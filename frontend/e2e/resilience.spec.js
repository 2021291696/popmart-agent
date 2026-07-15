// 看板韧性 e2e（数据中心化架构：看板只读 /api/boards/{page} 缓存，不再有本地演示副本降级）
import { test, expect, MOCK_BOARD_EXECUTIVE, MOCK_JOB_ID, BOARD_404_BODY } from './fixtures.js'

test.describe('看板韧性', () => {
  test('看板 404（从未分析）→ 空态引导而非白屏/崩溃', async ({ page }) => {
    await page.route(/\/api\/boards\/executive$/, (route) =>
      route.fulfill({ status: 404, json: BOARD_404_BODY })
    )
    await page.goto('/executive')
    const empty = page.locator('.board-empty')
    await expect(empty).toBeVisible({ timeout: 8000 })
    await expect(empty).toContainText('该看板尚无分析结果')
    // 空态不是错误卡，也不残留看板内容
    await expect(page.locator('.metric-card')).toHaveCount(0)
  })

  test('看板 500 → 错误卡；刷新分析 → 进度 → 完成跳回后恢复渲染（不残留旧错误）', async ({ page }) => {
    // 刷新 POST 前 GET 看板恒 500；refresh 翻转标记后 GET 返回正常缓存。
    // （不能用调用计数：React StrictMode 开发模式下挂载即双发请求，计数不可靠）
    let refreshed = false
    await page.route(/\/api\/boards\/executive\/refresh$/, (route) => {
      refreshed = true
      route.fulfill({ json: { job_id: MOCK_JOB_ID, status: 'pending', page: 'executive' }, status: 200 })
    })
    await page.route(/\/api\/boards\/executive$/, (route) => {
      if (!refreshed) route.fulfill({ status: 500, json: { detail: 'boom' } })
      else route.fulfill({ json: MOCK_BOARD_EXECUTIVE, status: 200 })
    })
    // 默认 job mock：completed + recommended_page=executive → 进度页自动跳回看板

    await page.goto('/executive')
    await expect(page.locator('.error-card')).toBeVisible({ timeout: 8000 })

    await page.click('.board-refresh-btn')
    // /progress/{job} → completed → 自动跳回 /executive → 重新 fetchBoard（第二次，200）
    await expect(page.locator('.metric-card').first()).toBeVisible({ timeout: 8000 })
    await expect(page).toHaveURL(/\/executive$/)
    await expect(page.locator('.error-card')).toHaveCount(0)
  })

  test('Landing 场景卡片按 /api/scenarios 渲染并展示预热徽标', async ({ page }) => {
    await page.goto('/')
    const cards = page.locator('.scenario-card')
    await expect(cards).toHaveCount(3)
    // fixtures 里 executive/supply 场景 cached: true
    await expect(page.locator('.scenario-cached-badge')).toHaveCount(2)
    await expect(page.locator('.scenario-cached-badge').first()).toContainText('已预热')
  })
})
