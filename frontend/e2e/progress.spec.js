// 进度页状态机 e2e（新契约：REST 终态 completed/failed；complete 跳 recommended_page 对应页面，不带 ?query=）
// 说明：SSE 在 playwright 里用一次性 body mock，断流后前端的「降级轮询」路径
// 与「SSE 直达」路径殊途同归（都走 getJob 刷新），这里通过 mock GET /api/jobs/{id}
// 的不同终态来验收状态机。
import { test, expect, mockJob, MOCK_JOB_ID } from './fixtures.js'

test.describe('进度页状态机', () => {
  test('已 completed 的 job（看板）→ 自动跳回对应看板页（不带 query 参数）', async ({ page }) => {
    await page.route(/\/api\/jobs\/[^/]+$/, (route) =>
      route.fulfill({ json: mockJob({ status: 'completed', recommended_page: 'supply' }), status: 200 })
    )
    await page.goto(`/progress/${MOCK_JOB_ID}`)
    await expect(page).toHaveURL(/\/supply$/, { timeout: 8000 })
    // 看板读自己的缓存，正常渲染
    await expect(page.locator('.timeline-dot').first()).toBeVisible({ timeout: 8000 })
  })

  test('已 completed 的 job（数据刷新 recommended_page=data）→ 自动跳 /data', async ({ page }) => {
    await page.route(/\/api\/jobs\/[^/]+$/, (route) =>
      route.fulfill({ json: mockJob({ status: 'completed', recommended_page: 'data' }), status: 200 })
    )
    await page.goto(`/progress/${MOCK_JOB_ID}`)
    await expect(page).toHaveURL(/\/data$/, { timeout: 8000 })
    // 数据页跳回后重新加载 overview
    await expect(page.locator('.data-overview-card').first()).toBeVisible({ timeout: 8000 })
  })

  test('failed job → 错误卡片 + 返回首页链接可见', async ({ page }) => {
    await page.route(/\/api\/jobs\/[^/]+$/, (route) =>
      route.fulfill({
        json: mockJob({ status: 'failed', error: 'LLM 调用超时', recommended_page: null }),
        status: 200,
      })
    )
    await page.goto(`/progress/${MOCK_JOB_ID}`)
    const card = page.locator('.error-card')
    await expect(card).toBeVisible({ timeout: 8000 })
    await expect(card).toContainText('分析失败')
    await expect(card).toContainText('LLM 调用超时')
    await expect(card.locator('a[href="/"]', { hasText: '返回首页' })).toBeVisible()
  })

  test('job 404（后端重启丢失）→ 显示「任务不存在或已过期」而非「分析失败」', async ({ page }) => {
    await page.route(/\/api\/jobs\/[^/]+$/, (route) =>
      route.fulfill({ status: 404, json: { detail: 'job not found' } })
    )
    await page.goto(`/progress/${MOCK_JOB_ID}`)
    const card = page.locator('.error-card')
    await expect(card).toBeVisible({ timeout: 8000 })
    await expect(card).toContainText('任务不存在或已过期')
    await expect(card).not.toContainText('分析失败')
  })
})
