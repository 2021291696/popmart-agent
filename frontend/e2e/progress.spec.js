// 进度页状态机 e2e（新契约：REST 终态 completed/failed）
// 说明：SSE 在 playwright 里用一次性 body mock，断流后前端的「降级轮询」路径
// 与「SSE 直达」路径殊途同归（都走 getJob 刷新），这里通过 mock GET /api/jobs/{id}
// 的不同终态来验收状态机，SSE 流式路径由 chat.spec.js 覆盖。
import { test, expect, mockJob, MOCK_JOB_ID } from './fixtures.js'

test.describe('进度页状态机', () => {
  test('已 completed 的 job 直接进入 /progress/:id → 自动跳转对应看板页', async ({ page }) => {
    // 初始 REST 即 completed + recommended_page → 不依赖 SSE 重放，直接视为完成态
    await page.route(/\/api\/jobs\/[^/]+$/, (route) =>
      route.fulfill({ json: mockJob({ status: 'completed', recommended_page: 'supply' }), status: 200 })
    )
    await page.goto(`/progress/${MOCK_JOB_ID}`)
    await expect(page).toHaveURL(/\/supply\?query=/, { timeout: 8000 })
  })

  test('failed job → 错误卡片 + 返回对话页重试按钮可见', async ({ page }) => {
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
    await expect(card.locator('a', { hasText: '返回对话页重试' })).toBeVisible()
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
