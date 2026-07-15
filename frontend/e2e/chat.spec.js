// 对话分析完整链路 e2e
import { test, expect, mockJob, MOCK_JOB_ID } from './fixtures.js'

test.describe('对话分析完整链路', () => {
  test('从 Chat 提交问题到进度页再到 Executive 看板', async ({ page }) => {
    // 覆盖默认 job 查询：首次轮询 running，之后 completed（走完 SSE → 刷新 → 跳转全链路）
    let jobPolls = 0
    await page.route(/\/api\/jobs\/[^/]+$/, async (route) => {
      jobPolls += 1
      await route.fulfill({
        json:
          jobPolls === 1
            ? mockJob({ status: 'running', recommended_page: null })
            : mockJob({ status: 'completed', recommended_page: 'executive' }),
        status: 200,
      })
    })

    await page.goto('/chat')
    await page.fill('.chat-input', '泡泡玛特最近的市场表现如何？')
    await page.click('button[type="submit"]')

    await expect(page).toHaveURL(new RegExp(`/progress/${MOCK_JOB_ID}`))
    // 事件驱动等待：SSE complete 帧 → getJob 刷新拿到 recommended_page → 跳转看板
    await expect(page).toHaveURL(/\/executive\?query=/, { timeout: 8000 })
  })
})
