// 数据页 e2e：抓取/整理/向量化状态总览 + 一键刷新
import { test, expect, mockJob, MOCK_JOB_ID } from './fixtures.js'

test.describe('数据页', () => {
  test('顶部概览卡渲染向量库与最近抓取/整理状态', async ({ page }) => {
    await page.goto('/data')
    await expect(page.locator('h1').first()).toContainText('数据')

    await expect(page.locator('.data-overview-card')).toHaveCount(5, { timeout: 8000 })
    const content = await page.content()
    expect(content).toContain('popmart_v3')
    expect(content).toContain('128')
    expect(content).toContain('2026-07-15 09:01') // 最近抓取
    expect(content).toContain('2026-07-15 09:05') // 最近整理
    expect(content).toContain('deepseek-chat')
  })

  test('数据源卡片渲染三类状态徽标与摘要', async ({ page }) => {
    await page.goto('/data')

    await expect(page.locator('.data-source-card')).toHaveCount(3, { timeout: 8000 })
    const content = await page.content()
    // 源名称与 kind 徽标
    expect(content).toContain('泡泡玛特官网首页')
    expect(content).toContain('官方')
    // 三种抓取状态：ok 绿 / never 灰 / http_N 红
    await expect(page.locator('.data-badge.ok').first()).toBeVisible()
    await expect(page.locator('.data-badge.never').first()).toBeVisible()
    await expect(page.locator('.data-badge.fail').first()).toContainText('http_502')
    // 已整理源的摘要预览与关键事实数
    expect(content).toContain('泡泡玛特成立于2010年')
    expect(content).toContain('8')
  })

  test('「刷新数据」→ 创建 job 并跳转进度页', async ({ page }) => {
    // job 保持 running：进度页不会因 complete 帧跳走，稳定停留在 /progress/{id}
    await page.route(/\/api\/jobs\/[^/]+$/, (route) =>
      route.fulfill({ json: mockJob({ status: 'running', recommended_page: null }), status: 200 })
    )
    await page.goto('/data')
    await expect(page.locator('.data-overview-card').first()).toBeVisible({ timeout: 8000 })

    await page.click('.data-toolbar button:has-text("刷新数据")')
    await expect(page).toHaveURL(new RegExp(`/progress/${MOCK_JOB_ID}`))
  })

  test('刷新冲突（409）→ 显示「已有刷新任务进行中」', async ({ page }) => {
    await page.route(/\/api\/data\/refresh$/, (route) =>
      route.fulfill({ status: 409, json: { detail: '已有数据刷新任务进行中' } })
    )
    await page.goto('/data')
    await expect(page.locator('.data-overview-card').first()).toBeVisible({ timeout: 8000 })

    await page.click('.data-toolbar button:has-text("刷新数据")')
    await expect(page.locator('.error-card')).toContainText('已有刷新任务进行中')
  })
})
