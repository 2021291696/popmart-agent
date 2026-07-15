import { chromium } from 'playwright'
import { mkdirSync } from 'fs'

mkdirSync('screenshots', { recursive: true })

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

const pages = [
  { path: '/', name: 'home' },
  { path: '/executive', name: 'executive' },
  { path: '/supply', name: 'supply' },
  { path: '/risk', name: 'risk' },
]

for (const { path, name } of pages) {
  await page.goto(`http://localhost:3000${path}`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(1200)
  await page.screenshot({ path: `screenshots/${name}.png`, fullPage: true })
  console.log(`screenshots/${name}.png`)
}

await browser.close()
