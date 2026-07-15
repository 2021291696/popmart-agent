/**
 * 面试动线真实端到端验收（无 mock，打真实 :3000 前端 + :8000 后端）
 * 产出：demo-screenshots/accept-flow-2026-07-14/*.png + 控制台错误日志
 * 运行：node scripts/accept-flow.cjs
 */
const { chromium } = require('@playwright/test')
const fs = require('fs')
const path = require('path')

const OUT_DIR = path.join(__dirname, '..', '..', 'demo-screenshots', 'accept-flow-2026-07-14')
const QUERY = '泡泡玛特未来一年最大的经营风险是什么？'

async function main() {
  fs.mkdirSync(OUT_DIR, { recursive: true })
  const consoleErrors = []
  const browser = await chromium.launch()
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 })
  page.on('console', (msg) => { if (msg.type() === 'error') consoleErrors.push(msg.text()) })
  page.on('pageerror', (err) => consoleErrors.push('PAGEERROR: ' + err.message))

  const shot = (name) => page.screenshot({ path: path.join(OUT_DIR, name), fullPage: false })

  // 1. 首页
  await page.goto('http://localhost:3000/', { waitUntil: 'networkidle' })
  await shot('01-landing.png')
  console.log('✅ 01 landing')

  // 2. 对话分析页
  await page.goto('http://localhost:3000/chat', { waitUntil: 'networkidle' })
  await shot('02-chat.png')
  console.log('✅ 02 chat')

  // 3. 输入问题并提交 → 进度页
  await page.fill('textarea', QUERY)
  await page.click('button[type="submit"]')
  await page.waitForURL(/\/progress\//, { timeout: 15000 })
  await page.waitForTimeout(4000) // 等 SSE 首批事件渲染
  await shot('03-progress-running.png')
  console.log('✅ 03 progress (running)')

  // 4. 等待自动跳转看板（真实分析 30-140s）
  await page.waitForURL(/\/(executive|supply|risk)\?query=/, { timeout: 240000 })
  await page.waitForTimeout(2500) // 等看板数据渲染
  await shot('04-dashboard-after-redirect.png')
  console.log('✅ 04 redirected to:', page.url())

  // 5. 历史数据页应出现新记录
  await page.goto('http://localhost:3000/history', { waitUntil: 'networkidle' })
  await page.waitForTimeout(1000)
  await shot('05-history.png')
  const historyText = await page.textContent('body')
  console.log(historyText.includes(QUERY) ? '✅ 05 history 含新记录' : '⚠️ 05 history 未见新记录')

  await browser.close()
  console.log('--- console errors:', consoleErrors.length)
  consoleErrors.slice(0, 10).forEach((e) => console.log('  ', e.slice(0, 200)))
}

main().catch((err) => { console.error('FAIL:', err.message); process.exit(1) })
