// 看板降级与韧性 e2e
import { test, expect, MOCK_EXECUTIVE, MOCK_SUPPLY, DEMO_QUERY } from './fixtures.js'

test.describe('看板韧性', () => {
  test('visualize 404（缓存为空）→ 看板显示错误页而非白屏/崩溃', async ({ page }) => {
    await page.route(/\/api\/visualize\/executive/, (route) =>
      route.fulfill({ status: 404, json: { detail: 'cache miss' } })
    )
    // 本地副本默认 404（fixtures），降级未命中 → 错误卡
    await page.goto('/executive?query=' + encodeURIComponent('不存在的查询'))
    const card = page.locator('.error-card')
    await expect(card).toBeVisible({ timeout: 8000 })
    await expect(card).toContainText('数据未就绪')
    await expect(card.locator('a[href="/chat"]')).toBeVisible()
  })

  test('看板页从 query A（失败）切到 query B（成功）→ 不残留 A 的错误', async ({ page }) => {
    const badQuery = '不存在的查询'
    await page.route(/\/api\/visualize\/supply/, (route) => {
      if (route.request().url().includes(encodeURIComponent(badQuery))) {
        route.fulfill({ status: 500, json: { detail: 'boom' } })
      } else {
        route.fulfill({ json: MOCK_SUPPLY, status: 200 })
      }
    })
    await page.goto('/supply?query=' + encodeURIComponent(badQuery))
    await expect(page.locator('.error-card')).toBeVisible({ timeout: 8000 })

    // 通过导航栏切到 /supply（无 query）：同一组件仅 searchParams 变化，不卸载重挂
    await page.click('nav >> text=备货分析')
    await expect(page.locator('.error-card')).toHaveCount(0)
    await expect(page.locator('.timeline-dot').first()).toBeVisible({ timeout: 8000 })
  })

  test('API 不可达但本地演示副本命中 → 渲染降级数据 + DemoBanner', async ({ page }) => {
    await page.route(/\/api\/visualize\/executive/, (route) =>
      route.fulfill({ status: 500, json: { detail: 'API down' } })
    )
    await page.route(/\/data\/cache\.json/, (route) =>
      route.fulfill({
        json: { executive: { [DEMO_QUERY]: MOCK_EXECUTIVE }, supply: {}, risk: {} },
        status: 200,
      })
    )
    await page.goto('/executive?query=' + encodeURIComponent(DEMO_QUERY))
    await expect(page.locator('.demo-banner')).toContainText('离线演示数据')
    await expect(page.locator('.metric-card').first()).toBeVisible({ timeout: 8000 })
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
