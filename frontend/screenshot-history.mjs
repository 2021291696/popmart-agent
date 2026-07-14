import { chromium } from 'playwright'
import { mkdirSync } from 'fs'

mkdirSync('screenshots', { recursive: true })

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

await page.route('**/api/history', async (route) => {
  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      count: 3,
      items: [
        {
          query: '泡泡玛特最近的市场表现如何？',
          saved_at: '2026-07-14 14:30',
          total_agents: 2,
          elapsed_seconds: 132.8,
          snippet: '## 核心结论\n1. 泡泡玛特 2025 年业绩爆发式增长...',
          recommended_page: 'executive',
        },
        {
          query: 'LABUBU 为什么能成为泡泡玛特的核心IP？',
          saved_at: '2026-07-14 13:15',
          total_agents: 1,
          elapsed_seconds: 45.2,
          snippet: 'LABUBU 近30天提及量占比48.5%，远超MOLLY...',
          recommended_page: 'supply',
        },
        {
          query: '泡泡玛特消费者投诉和二手假货风险有多高？',
          saved_at: '2026-07-14 11:20',
          total_agents: 2,
          elapsed_seconds: 60.0,
          snippet: '消费者投诉和二手假货风险处于中高水平...',
          recommended_page: 'risk',
        },
      ],
    }),
  })
})

await page.goto('http://localhost:3000/history', { waitUntil: 'networkidle' })
await page.waitForTimeout(800)
await page.screenshot({ path: 'screenshots/history.png', fullPage: true })
console.log('screenshots/history.png')

await browser.close()
