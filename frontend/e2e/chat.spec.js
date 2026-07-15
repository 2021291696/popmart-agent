// 对话分析页 e2e：会话式 RAG 聊天客户端（不再跳 /progress）
import { test, expect, MOCK_CHAT_ANSWER, MOCK_CHAT_SESSION } from './fixtures.js'

test.describe('对话分析页', () => {
  test('发送消息 → 用户气泡 + 助手气泡（来源 chips + 置信度），侧栏出现新会话', async ({ page }) => {
    // 会话列表初始为空；POST /api/chat 成功后后端生成会话，侧栏刷新出现新会话
    let sessions = []
    await page.route(/\/api\/chat\/sessions$/, (route) =>
      route.fulfill({ json: { items: sessions }, status: 200 })
    )
    await page.route(/\/api\/chat$/, (route) => {
      if (route.request().method() === 'POST') {
        sessions = [{ ...MOCK_CHAT_SESSION }]
        route.fulfill({ json: MOCK_CHAT_ANSWER, status: 200 })
      } else {
        route.fallback()
      }
    })

    await page.goto('/chat')
    await expect(page.locator('.chat-session-item')).toHaveCount(0)
    await expect(page.locator('.chat-welcome')).toBeVisible()

    await page.fill('.chat-input', '泡泡玛特的核心IP有哪些？')
    await page.click('.chat-send-btn')

    // 用户气泡靠右一条 + 助手气泡一条（含回答正文）
    await expect(page.locator('.chat-bubble.user')).toHaveCount(1)
    const assistant = page.locator('.chat-bubble.assistant').first()
    await expect(assistant).toContainText('LABUBU')

    // 置信度标签 + 来源 chips
    await expect(assistant.locator('.chat-chip.confidence')).toContainText('确定')
    await expect(assistant.locator('.chat-chip.source')).toHaveCount(2)

    // 侧栏刷新后出现新会话
    await expect(page.locator('.chat-session-item')).toHaveCount(1)
    await expect(page.locator('.chat-session-item').first()).toContainText('泡泡玛特的核心IP')
  })

  test('点击侧栏会话 → 加载完整历史消息', async ({ page }) => {
    // 默认 mock：列表 1 个会话，详情含 1 轮问答
    await page.goto('/chat')
    await page.click('.chat-session-item')

    await expect(page.locator('.chat-bubble.user')).toHaveCount(1)
    await expect(page.locator('.chat-bubble.assistant')).toHaveCount(1)
    await expect(page.locator('.chat-bubble.assistant')).toContainText('LABUBU')
    // 历史助手消息同样渲染来源 chips
    await expect(page.locator('.chat-chip.source')).toHaveCount(2)
  })

  test('新会话按钮 → 清空对话区回到欢迎态', async ({ page }) => {
    await page.goto('/chat')
    await page.click('.chat-session-item')
    await expect(page.locator('.chat-bubble.user')).toHaveCount(1)

    await page.click('.chat-new-btn')
    await expect(page.locator('.chat-bubble')).toHaveCount(0)
    await expect(page.locator('.chat-welcome')).toBeVisible()
  })

  test('LLM 失败（502）→ 错误提示气泡，已发送的用户消息保留', async ({ page }) => {
    await page.route(/\/api\/chat$/, (route) =>
      route.fulfill({ status: 502, json: { detail: 'LLM 调用失败: upstream timeout' } })
    )
    await page.goto('/chat')
    await page.fill('.chat-input', '测试问题')
    await page.click('.chat-send-btn')

    await expect(page.locator('.chat-bubble.user')).toHaveCount(1)
    await expect(page.locator('.chat-error')).toContainText('LLM 调用失败')
  })
})
