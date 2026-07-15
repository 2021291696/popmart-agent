import { chromium } from 'playwright'
import { mkdirSync } from 'fs'

mkdirSync('screenshots', { recursive: true })

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

// 拦截 API，模拟一次完整分析
await page.route('**/api/jobs', async (route) => {
  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ job_id: 'job-demo', status: 'pending', query: '泡泡玛特最近的市场表现如何？' }),
  })
})

await page.route('**/api/jobs/job-demo', async (route) => {
  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      id: 'job-demo',
      status: 'completed',
      query: '泡泡玛特最近的市场表现如何？',
      recommended_page: 'executive',
    }),
  })
})

await page.route('**/api/jobs/job-demo/events', async (route) => {
  await route.fulfill({
    status: 200,
    contentType: 'text/event-stream',
    body: [
      `data: ${JSON.stringify({ stage: 'decompose', message: '已分解为 2 个子任务' })}`,
      `data: ${JSON.stringify({ stage: 'agent_complete', message: 'ip_intelligence 完成分析' })}`,
      `data: ${JSON.stringify({ stage: 'agent_complete', message: 'consumer_insights 完成分析' })}`,
      `data: ${JSON.stringify({ stage: 'conflict_detect', message: '检测到 0 个冲突' })}`,
      `data: ${JSON.stringify({ stage: 'synthesize', message: '综合报告已生成' })}`,
      `data: ${JSON.stringify({ stage: 'complete', message: '分析完成' })}`,
    ].join('\n\n') + '\n\n',
  })
})

await page.route('**/api/visualize/executive?query=*', async (route) => {
  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      query: '泡泡玛特最近的市场表现如何？',
      title: '泡泡玛特综合分析',
      agents: [
        { name: 'ip_intelligence', conclusion: 'LABUBU 热度持续上升', steps: 4, llm_calls: 4, sources_count: 3 },
        { name: 'consumer_insights', conclusion: '复购率稳步提升', steps: 3, llm_calls: 3, sources_count: 2 },
      ],
      total_agents: 2,
      total_steps: 7,
      total_llm_calls: 7,
      elapsed_seconds: 45.2,
      final_answer: '## 核心结论\n1. 泡泡玛特 2025 年业绩爆发式增长。\n2. 海外市场是增长核心引擎。',
      generated_at: '2026-07-14',
    }),
  })
})

const pages = [
  { path: '/', name: 'home' },
  { path: '/chat', name: 'chat' },
]

for (const { path, name } of pages) {
  await page.goto(`http://localhost:3000${path}`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(800)
  await page.screenshot({ path: `screenshots/${name}.png`, fullPage: true })
  console.log(`screenshots/${name}.png`)
}

// 进入 Progress 页面
await page.goto('http://localhost:3000/chat', { waitUntil: 'networkidle' })
await page.fill('.chat-input', '泡泡玛特最近的市场表现如何？')
await page.click('button[type="submit"]')
await page.waitForURL(/\/progress\/job-demo/, { timeout: 5000 })
await page.waitForTimeout(1200)
await page.screenshot({ path: 'screenshots/progress.png', fullPage: true })
console.log('screenshots/progress.png')

// Progress 完成后会跳转到 executive
await page.waitForURL(/\/executive\?query=/, { timeout: 5000 })
await page.waitForTimeout(800)
await page.screenshot({ path: 'screenshots/executive.png', fullPage: true })
console.log('screenshots/executive.png')

await browser.close()
