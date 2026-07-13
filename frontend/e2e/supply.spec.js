// Supply 页面 e2e 测试 - ReAct 推理时间线
import { test, expect } from './fixtures.js'

test.describe('Supply 页面 - ReAct 推理时间线', () => {
  test('页面加载显示标题', async ({ page }) => {
    await page.goto('/supply')
    await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 5000 })
  })

  test('显示 ReAct 时间线步骤（Step 1, 2, 3）', async ({ page }) => {
    await page.goto('/supply')

    // 等待 timeline 渲染
    await page.waitForTimeout(1000)

    const content = await page.content()
    // 至少 3 个 step
    expect(content).toContain('Step 1')
    expect(content).toContain('Step 2')
    expect(content).toContain('Step 3')
  })

  test('时间线包含 Thought/Action/Observation 三要素', async ({ page }) => {
    await page.goto('/supply')
    await page.waitForTimeout(1000)

    const content = await page.content()
    expect(content).toContain('Thought')
    expect(content).toContain('Action')
    expect(content).toContain('Observation')
  })

  test('显示工具调用统计表格', async ({ page }) => {
    await page.goto('/supply')
    await page.waitForTimeout(1000)

    const content = await page.content()
    expect(content).toContain('web_search')
    expect(content).toContain('sentiment_analyze')
    expect(content).toContain('trend_compare')
  })

  test('显示最终结论', async ({ page }) => {
    await page.goto('/supply')
    await page.waitForTimeout(1000)

    const content = await page.content()
    expect(content).toContain('稀缺性营销')
  })
})