// 通用 e2e 测试：路由 + 导航 + 错误处理
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

  test('/history 路由已移除 → 显示 404 页', async ({ page }) => {
    await page.goto('/history')
    await expect(page.locator('.not-found')).toContainText(/404|不存在/, { timeout: 5000 })
  })

  test('导航栏「数据」链接进入数据页', async ({ page }) => {
    await page.goto('/')
    await page.click('nav >> text=数据')
    await expect(page).toHaveURL(/\/data$/)
    await expect(page.locator('.data-overview-card').first()).toBeVisible({ timeout: 8000 })
  })

  test('看板 API 500 → 显示错误提示（不白屏）', async ({ page }) => {
    await page.route(/\/api\/boards\/executive$/, (route) =>
      route.fulfill({ status: 500, json: { detail: 'Server Error' } })
    )
    await page.goto('/executive')

    // 应该显示错误提示而非崩溃
    await expect(page.locator('.error-card')).toBeVisible({ timeout: 8000 })
    await expect(page.locator('.error-card')).toContainText(/加载失败|错误|失败/)
  })
})
