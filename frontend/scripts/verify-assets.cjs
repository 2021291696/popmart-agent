// 验证 4 个业务页面 — 截图 + 断言无 "需要图片/需要地图/需要图表" 文字
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const OUT_DIR = path.join(__dirname, '..', 'demo-screenshots', 'asset-verify-2026-07-13');
if (!fs.existsSync(OUT_DIR)) fs.mkdirSync(OUT_DIR, { recursive: true});

const PAGES = [
  {name: '01-landing', url: 'http://localhost:3000/'},
  {name: '02-executive', url: 'http://localhost:3000/executive'},
  {name: '03-supply', url: 'http://localhost:3000/supply'},
  {name: '04-risk', url: 'http://localhost:3000/risk'},
];

const PLACEHOLDER_PHRASES = ['需要图片', '需要地图', '需要图表', '需要 ECharts', 'placeholder-label'];

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({viewport: {width: 1440, height: 900}});
  const results = [];

  for (const p of PAGES) {
    const page = await ctx.newPage();
    try {
      await page.goto(p.url, {waitUntil: 'networkidle', timeout: 30000});
    } catch (e) {
      // SPA 异步 fetch 数据，可能 networkidle 永不达成 — 降级用 load
      await page.goto(p.url, {waitUntil: 'load', timeout: 30000});
    }
    // 额外等 5s 让 recharts 渲染
    await page.waitForTimeout(5000);

    const png = path.join(OUT_DIR, p.name + '.png');
    await page.screenshot({path: png, fullPage: true});

    // 只检测用户能看见的中文提示文字 — 用 page.locator 找元素
    const hits = [];
    for (const ph of PLACEHOLDER_PHRASES) {
      const count = await page.locator(`text=${ph}`).count();
      if (count > 0) hits.push(ph);
    }

    // 找所有 <img> src
    const imgs = await page.$$eval('img', els => els.map(e => ({
      src: e.getAttribute('src'),
      alt: e.getAttribute('alt'),
      naturalWidth: e.naturalWidth,
      naturalHeight: e.naturalHeight,
    })));

    // 找 recharts
    const svgCount = await page.locator('svg.recharts-surface').count();

    results.push({
      page: p.name,
      url: p.url,
      png,
      placeholderHits: hits,
      imgs: imgs.filter(i => i.src && !i.src.startsWith('data:')),
      rechartsCount: svgCount,
    });
    await page.close();
    console.log(`[${p.name}] placeholders=${hits.length} imgs=${imgs.length} recharts=${svgCount}`);
  }

  await browser.close();
  console.log('\n=== Summary ===');
  for (const r of results) {
    console.log(`${r.page}: png=${r.png}`);
    console.log(`  imgs:`, r.imgs.map(i => `${i.src} (${i.naturalWidth}x${i.naturalHeight})`).join(', '));
    console.log(`  recharts: ${r.rechartsCount}`);
    if (r.placeholderHits.length) console.log(`  ⚠️ placeholder phrases: ${r.placeholderHits.join(', ')}`);
  }
})();
