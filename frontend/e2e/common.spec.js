// 通用 e2e 测试：路由 + 错误处理 + 降级
import { test, expect } from './fixtures.js'

test.describe('通用页面行为', () => {
  test('Landing 页正常加载', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 5000 })
  })

  test('NotFound 页对不存在路由显示', async ({ page }) => {
    await page.goto('/nonexistent-page-xyz')
    await expect(page.locator('.not-found')).toContainText(/404|不存在/, { timeout: 5000 })
  })

  test('API 失败且本地副本未命中时显示错误提示（不白屏）', async ({ page }) => {
    // 重新 route 让 API 返回错误（本地副本默认 404 → 降级未命中）
    await page.route(/\/api\/visualize\/executive/, (route) =>
      route.fulfill({ status: 500, json: { detail: 'Server Error' } })
    )
    await page.goto('/executive')

    // 应该显示错误提示而非崩溃
    await expect(page.locator('.error-card')).toBeVisible({ timeout: 8000 })
    await expect(page.locator('.error-card')).toContainText(/数据未就绪|错误|失败/)
  })
})
