// 对话分析完整链路 e2e
import { test, expect } from './fixtures.js'

test.describe('对话分析完整链路', () => {
  test('从 Chat 提交问题到进度页再到 Executive 看板', async ({ page }) => {
    await page.route('**/api/jobs', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          job_id: 'job-123',
          status: 'pending',
          query: '泡泡玛特市场表现如何？',
        }),
      })
    })

    await page.route('**/api/jobs/job-123', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'job-123',
          status: 'completed',
          query: '泡泡玛特市场表现如何？',
          recommended_page: 'executive',
        }),
      })
    })

    await page.route('**/api/jobs/job-123/events', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: `data: ${JSON.stringify({ stage: 'complete', message: 'done' })}\n\n`,
      })
    })

    await page.route('**/api/visualize/executive?query=*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          query: '泡泡玛特市场表现如何？',
          title: '泡泡玛特综合分析',
          agents: [],
          total_agents: 0,
          total_steps: 0,
          total_llm_calls: 0,
          elapsed_seconds: 0,
          final_answer: 'test',
          generated_at: '2026-07-14',
        }),
      })
    })

    await page.goto('/chat')
    await page.fill('.chat-input', '泡泡玛特市场表现如何？')
    await page.click('button[type="submit"]')

    await expect(page).toHaveURL(/\/progress\/job-123/)
    await page.waitForTimeout(500)
    await expect(page).toHaveURL(/\/executive\?query=/)
  })
})
