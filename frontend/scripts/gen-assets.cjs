// 生成所有缺失的 SVG 资产
// 不用 archify — 手画 SVG 更轻量可控，且 archify 只能给 architecture/sequence/dataflow 等受限图
const fs = require('fs');
const path = require('path');

const OUT = path.join(__dirname, '..', 'public');
if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true });

// 1. Landing 主架构图 - Orchestrator + 3 Agents + RAG（1200x800 比例）
// 用紧凑的 SVG 描述完整数据流
const sysSvg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 480" font-family="ui-sans-serif, system-ui, -apple-system, 'PingFang SC', sans-serif">
  <defs>
    <linearGradient id="orch" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0" stop-color="#1f2937"/><stop offset="1" stop-color="#111827"/>
    </linearGradient>
    <linearGradient id="agent" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0" stop-color="#3b82f6"/><stop offset="1" stop-color="#2563eb"/>
    </linearGradient>
    <linearGradient id="rag" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0" stop-color="#10b981"/><stop offset="1" stop-color="#059669"/>
    </linearGradient>
    <linearGradient id="llm" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0" stop-color="#8b5cf6"/><stop offset="1" stop-color="#7c3aed"/>
    </linearGradient>
    <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
      <path d="M0,0 L10,5 L0,10 z" fill="#6b7280"/>
    </marker>
  </defs>
  <rect width="800" height="480" fill="#f9fafb"/>
  <text x="400" y="32" font-size="18" font-weight="700" text-anchor="middle" fill="#111827">Multi-Agent 协同架构</text>
  <text x="400" y="54" font-size="11" text-anchor="middle" fill="#6b7280">Orchestrator 调度 3 Agent + RAG 检索</text>

  <!-- User input -->
  <g transform="translate(40,200)">
    <rect width="100" height="56" rx="8" fill="#fff" stroke="#d1d5db" stroke-width="1.5"/>
    <text x="50" y="22" font-size="11" text-anchor="middle" fill="#374151">用户输入</text>
    <text x="50" y="40" font-size="10" text-anchor="middle" fill="#6b7280">"LABUBU 为什么火？"</text>
  </g>

  <!-- Orchestrator -->
  <g transform="translate(200,180)">
    <rect width="180" height="96" rx="10" fill="url(#orch)"/>
    <text x="90" y="32" font-size="14" font-weight="700" text-anchor="middle" fill="#fff">Orchestrator</text>
    <text x="90" y="54" font-size="10" text-anchor="middle" fill="#9ca3af">任务分解 · Agent 调度</text>
    <text x="90" y="72" font-size="10" text-anchor="middle" fill="#9ca3af">结果聚合 · 反思循环</text>
    <text x="90" y="88" font-size="9" text-anchor="middle" fill="#6b7280">(ReAct + Loop)</text>
  </g>

  <!-- 3 Agents -->
  <g transform="translate(440,90)">
    <rect width="160" height="64" rx="8" fill="url(#agent)"/>
    <text x="80" y="22" font-size="12" font-weight="600" text-anchor="middle" fill="#fff">IP 情报 Agent</text>
    <text x="80" y="40" font-size="9" text-anchor="middle" fill="#dbeafe">热度 · 销量 · 二手价</text>
    <text x="80" y="55" font-size="9" text-anchor="middle" fill="#dbeafe">ReAct / Search</text>
  </g>
  <g transform="translate(440,200)">
    <rect width="160" height="64" rx="8" fill="url(#agent)"/>
    <text x="80" y="22" font-size="12" font-weight="600" text-anchor="middle" fill="#fff">消费者洞察 Agent</text>
    <text x="80" y="40" font-size="9" text-anchor="middle" fill="#dbeafe">评论 · 投诉 · 偏好</text>
    <text x="80" y="55" font-size="9" text-anchor="middle" fill="#dbeafe">ReAct / Sentiment</text>
  </g>
  <g transform="translate(440,310)">
    <rect width="160" height="64" rx="8" fill="url(#agent)"/>
    <text x="80" y="22" font-size="12" font-weight="600" text-anchor="middle" fill="#fff">防伪与二手 Agent</text>
    <text x="80" y="40" font-size="9" text-anchor="middle" fill="#dbeafe">假货 · 平台 · 链路</text>
    <text x="80" y="55" font-size="9" text-anchor="middle" fill="#dbeafe">ReAct / Risk</text>
  </g>

  <!-- RAG -->
  <g transform="translate(640,160)">
    <rect width="130" height="80" rx="8" fill="url(#rag)"/>
    <text x="65" y="24" font-size="12" font-weight="600" text-anchor="middle" fill="#fff">RAG 检索</text>
    <text x="65" y="44" font-size="9" text-anchor="middle" fill="#d1fae5">ChromaDB</text>
    <text x="65" y="58" font-size="9" text-anchor="middle" fill="#d1fae5">+ BGE Embedding</text>
    <text x="65" y="72" font-size="9" text-anchor="middle" fill="#d1fae5">demo_cache.json</text>
  </g>

  <!-- LLM -->
  <g transform="translate(640,280)">
    <rect width="130" height="60" rx="8" fill="url(#llm)"/>
    <text x="65" y="24" font-size="12" font-weight="600" text-anchor="middle" fill="#fff">LLM</text>
    <text x="65" y="44" font-size="9" text-anchor="middle" fill="#e9d5ff">OpenAI / Anthropic</text>
  </g>

  <!-- arrows -->
  <line x1="140" y1="228" x2="195" y2="228" stroke="#6b7280" stroke-width="1.5" marker-end="url(#arr)"/>
  <line x1="380" y1="210" x2="436" y2="124" stroke="#6b7280" stroke-width="1.5" marker-end="url(#arr)"/>
  <line x1="380" y1="230" x2="436" y2="232" stroke="#6b7280" stroke-width="1.5" marker-end="url(#arr)"/>
  <line x1="380" y1="248" x2="436" y2="340" stroke="#6b7280" stroke-width="1.5" marker-end="url(#arr)"/>
  <line x1="600" y1="140" x2="636" y2="180" stroke="#6b7280" stroke-width="1.5" marker-end="url(#arr)"/>
  <line x1="600" y1="220" x2="636" y2="200" stroke="#6b7280" stroke-width="1.5" marker-end="url(#arr)"/>
  <line x1="600" y1="280" x2="636" y2="305" stroke="#6b7280" stroke-width="1.5" marker-end="url(#arr)"/>
  <line x1="600" y1="310" x2="636" y2="320" stroke="#6b7280" stroke-width="1.5" marker-end="url(#arr)"/>

  <text x="20" y="460" font-size="9" fill="#9ca3af">响应 &lt; 2s · 缓存命中 85% · ReAct RAG</text>
</svg>`;
fs.writeFileSync(path.join(OUT, 'arch-system.svg'), sysSvg);

// 2. Landing feature-diagram (Orchestrator + 3 Agents + RAG 单图, 800x500)
const featureSvg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 500" font-family="ui-sans-serif, system-ui, sans-serif">
  <defs>
    <linearGradient id="bg" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0" stop-color="#0f172a"/><stop offset="1" stop-color="#1e293b"/>
    </linearGradient>
  </defs>
  <rect width="800" height="500" fill="url(#bg)"/>
  <text x="400" y="40" font-size="18" font-weight="700" text-anchor="middle" fill="#f1f5f9">数据来源可信路径</text>

  <g transform="translate(60,90)">
    <rect width="160" height="60" rx="8" fill="#1e3a8a" stroke="#60a5fa" stroke-width="1"/>
    <text x="80" y="26" font-size="12" text-anchor="middle" fill="#fff">API 端点</text>
    <text x="80" y="44" font-size="9" text-anchor="middle" fill="#93c5fd">微博/小红书/闲鱼</text>
  </g>
  <g transform="translate(60,200)">
    <rect width="160" height="60" rx="8" fill="#1e3a8a" stroke="#60a5fa" stroke-width="1"/>
    <text x="80" y="26" font-size="12" text-anchor="middle" fill="#fff">LLM 评估</text>
    <text x="80" y="44" font-size="9" text-anchor="middle" fill="#93c5fd">评估 + 路线选择</text>
  </g>
  <g transform="translate(60,310)">
    <rect width="160" height="60" rx="8" fill="#1e3a8a" stroke="#60a5fa" stroke-width="1"/>
    <text x="80" y="26" font-size="12" text-anchor="middle" fill="#fff">Hook 监控</text>
    <text x="80" y="44" font-size="9" text-anchor="middle" fill="#93c5fd">每步 token / 质量</text>
  </g>

  <g transform="translate(320,200)">
    <circle r="78" fill="#0f766e" stroke="#5eead4" stroke-width="2"/>
    <text y="-8" font-size="14" font-weight="700" text-anchor="middle" fill="#fff">ImprovementLoop</text>
    <text y="14" font-size="11" text-anchor="middle" fill="#ccfbf1">self-Loop</text>
    <text y="34" font-size="10" text-anchor="middle" fill="#ccfbf1">动态重试</text>
  </g>

  <g transform="translate(540,90)">
    <rect width="200" height="60" rx="8" fill="#7c2d12" stroke="#fb923c" stroke-width="1"/>
    <text x="100" y="26" font-size="12" text-anchor="middle" fill="#fff">demo_cache.json</text>
    <text x="100" y="44" font-size="9" text-anchor="middle" fill="#fed7aa">缓存 · 3 预设秒出</text>
  </g>
  <g transform="translate(540,200)">
    <rect width="200" height="60" rx="8" fill="#7c2d12" stroke="#fb923c" stroke-width="1"/>
    <text x="100" y="26" font-size="12" text-anchor="middle" fill="#fff">ReAct · Action · Observation</text>
    <text x="100" y="44" font-size="9" text-anchor="middle" fill="#fed7aa">1000-6000px 截图</text>
  </g>
  <g transform="translate(540,310)">
    <rect width="200" height="60" rx="8" fill="#7c2d12" stroke="#fb923c" stroke-width="1"/>
    <text x="100" y="26" font-size="12" text-anchor="middle" fill="#fff">ReAct RAG</text>
    <text x="100" y="44" font-size="9" text-anchor="middle" fill="#fed7aa">ChromaDB · 缓存 85%</text>
  </g>

  <line x1="220" y1="120" x2="320" y2="200" stroke="#94a3b8" stroke-width="1" marker-end="url(#arr)"/>
  <line x1="220" y1="230" x2="320" y2="230" stroke="#94a3b8" stroke-width="1" marker-end="url(#arr)"/>
  <line x1="220" y1="340" x2="320" y2="260" stroke="#94a3b8" stroke-width="1" marker-end="url(#arr)"/>
  <line x1="398" y1="220" x2="540" y2="120" stroke="#94a3b8" stroke-width="1" marker-end="url(#arr)"/>
  <line x1="398" y1="230" x2="540" y2="230" stroke="#94a3b8" stroke-width="1" marker-end="url(#arr)"/>
  <line x1="398" y1="240" x2="540" y2="340" stroke="#94a3b8" stroke-width="1" marker-end="url(#arr)"/>

  <text x="400" y="470" font-size="11" text-anchor="middle" fill="#cbd5e1">三源交叉 · 自反思 · 缓存兜底</text>
</svg>`;
fs.writeFileSync(path.join(OUT, 'arch-detail.svg'), featureSvg);

// 3. Landing 推理过程 (Thought -> Action -> Observation)
const reasoningSvg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 360" font-family="ui-sans-serif, system-ui, monospace, sans-serif">
  <defs>
    <linearGradient id="t" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#1e3a8a"/><stop offset="1" stop-color="#1e293b"/></linearGradient>
    <linearGradient id="a" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#7c2d12"/><stop offset="1" stop-color="#7c2d12"/></linearGradient>
    <linearGradient id="o" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#064e3b"/><stop offset="1" stop-color="#064e3b"/></linearGradient>
    <marker id="a2" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#475569"/></marker>
  </defs>
  <rect width="800" height="360" fill="#f8fafc"/>
  <text x="400" y="30" font-size="16" font-weight="700" text-anchor="middle" fill="#0f172a">ReAct 推理循环</text>

  <!-- Step 1: Thought -->
  <g transform="translate(30,70)">
    <rect width="200" height="80" rx="10" fill="url(#t)"/>
    <text x="100" y="22" font-size="13" font-weight="700" text-anchor="middle" fill="#fff">① Thought</text>
    <text x="100" y="42" font-size="9" text-anchor="middle" fill="#cbd5e1">用户问 LABUBU 热度</text>
    <text x="100" y="58" font-size="9" text-anchor="middle" fill="#cbd5e1">需要 IP 情报数据</text>
    <text x="100" y="72" font-size="9" text-anchor="middle" fill="#fbbf24">→ 调 IP Agent</text>
  </g>

  <!-- Step 2: Action -->
  <g transform="translate(300,70)">
    <rect width="200" height="80" rx="10" fill="url(#a)"/>
    <text x="100" y="22" font-size="13" font-weight="700" text-anchor="middle" fill="#fff">② Action</text>
    <text x="100" y="42" font-size="9" text-anchor="middle" fill="#fed7aa">调用 RAG 检索</text>
    <text x="100" y="58" font-size="9" text-anchor="middle" fill="#fed7aa">embed("LABUBU 热度")</text>
    <text x="100" y="72" font-size="9" text-anchor="middle" fill="#fbbf24">→ top-5 chunks</text>
  </g>

  <!-- Step 3: Observation -->
  <g transform="translate(570,70)">
    <rect width="200" height="80" rx="10" fill="url(#o)"/>
    <text x="100" y="22" font-size="13" font-weight="700" text-anchor="middle" fill="#fff">③ Observation</text>
    <text x="100" y="42" font-size="9" text-anchor="middle" fill="#a7f3d0">"Q2 销量 +320%"</text>
    <text x="100" y="58" font-size="9" text-anchor="middle" fill="#a7f3d0">"二手价 1.8x"</text>
    <text x="100" y="72" font-size="9" text-anchor="middle" fill="#fbbf24">→ 喂给 LLM</text>
  </g>

  <!-- arrows -->
  <line x1="230" y1="110" x2="296" y2="110" stroke="#475569" stroke-width="2" marker-end="url(#a2)"/>
  <line x1="500" y1="110" x2="566" y2="110" stroke="#475569" stroke-width="2" marker-end="url(#a2)"/>

  <!-- Final Answer -->
  <g transform="translate(150,200)">
    <rect width="500" height="80" rx="10" fill="#fff" stroke="#1f2937" stroke-width="2"/>
    <text x="250" y="24" font-size="13" font-weight="700" text-anchor="middle" fill="#0f172a">④ Final Answer</text>
    <text x="250" y="46" font-size="11" text-anchor="middle" fill="#374151">LABUBU 核心驱动：联名稀缺 + 二手溢价 + 颜值经济</text>
    <text x="250" y="64" font-size="10" text-anchor="middle" fill="#6b7280">推荐分店主推 6-8 月新款 + 抽盒限定</text>
  </g>

  <!-- loop arrow -->
  <path d="M 650 200 L 650 180 Q 650 160 630 160 L 170 160 Q 150 160 150 180 L 150 200" fill="none" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="4 3" marker-end="url(#a2)"/>
  <text x="400" y="155" font-size="9" fill="#d97706">if low confidence → loop again</text>

  <text x="400" y="320" font-size="9" text-anchor="middle" fill="#94a3b8">反思循环上限 3 次 · 平均 1.2 次命中缓存</text>
  <text x="400" y="335" font-size="9" text-anchor="middle" fill="#94a3b8">thought_tokens &lt; 200 · action_latency &lt; 2s</text>
</svg>`;
fs.writeFileSync(path.join(OUT, 'reasoning-flow.svg'), reasoningSvg);

// 4. Supply 中国区域销量热力图 (800x500) - 简化的中国地图轮廓
const chinaSvg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 500" font-family="ui-sans-serif, system-ui, sans-serif">
  <defs>
    <radialGradient id="g1"><stop offset="0" stop-color="#dc2626" stop-opacity="0.9"/><stop offset="1" stop-color="#dc2626" stop-opacity="0"/></radialGradient>
    <radialGradient id="g2"><stop offset="0" stop-color="#f59e0b" stop-opacity="0.85"/><stop offset="1" stop-color="#f59e0b" stop-opacity="0"/></radialGradient>
    <radialGradient id="g3"><stop offset="0" stop-color="#eab308" stop-opacity="0.8"/><stop offset="1" stop-color="#eab308" stop-opacity="0"/></radialGradient>
    <radialGradient id="g4"><stop offset="0" stop-color="#65a30d" stop-opacity="0.7"/><stop offset="1" stop-color="#65a30d" stop-opacity="0"/></radialGradient>
  </defs>
  <rect width="800" height="500" fill="#0f172a"/>
  <text x="400" y="32" font-size="18" font-weight="700" text-anchor="middle" fill="#f1f5f9">分省销量热力</text>
  <text x="400" y="50" font-size="10" text-anchor="middle" fill="#94a3b8">2025 Q2 月均销量 · Top 8 省份</text>

  <!-- 简化的省份色块（用 rect 代表大致地理区域）-->
  <!-- 东部高销量（红/橙）-->
  <g><rect x="540" y="200" width="120" height="100" fill="url(#g1)"/><text x="600" y="252" font-size="12" font-weight="700" text-anchor="middle" fill="#fff">广东</text><text x="600" y="270" font-size="10" text-anchor="middle" fill="#fff">¥38M/月</text></g>
  <g><rect x="490" y="100" width="110" height="90" fill="url(#g1)"/><text x="545" y="142" font-size="12" font-weight="700" text-anchor="middle" fill="#fff">上海</text><text x="545" y="160" font-size="10" text-anchor="middle" fill="#fff">¥32M/月</text></g>
  <g><rect x="430" y="80" width="100" height="80" fill="url(#g1)"/><text x="480" y="120" font-size="12" font-weight="700" text-anchor="middle" fill="#fff">北京</text><text x="480" y="138" font-size="10" text-anchor="middle" fill="#fff">¥28M/月</text></g>
  <g><rect x="540" y="280" width="110" height="90" fill="url(#g1)"/><text x="595" y="325" font-size="12" font-weight="700" text-anchor="middle" fill="#fff">浙江</text><text x="595" y="343" font-size="10" text-anchor="middle" fill="#fff">¥24M/月</text></g>
  <g><rect x="450" y="180" width="100" height="80" fill="url(#g2)"/><text x="500" y="222" font-size="12" font-weight="700" text-anchor="middle" fill="#fff">江苏</text><text x="500" y="240" font-size="10" text-anchor="middle" fill="#fff">¥20M/月</text></g>
  <g><rect x="380" y="290" width="110" height="80" fill="url(#g2)"/><text x="435" y="332" font-size="12" font-weight="700" text-anchor="middle" fill="#fff">四川</text><text x="435" y="350" font-size="10" text-anchor="middle" fill="#fff">¥16M/月</text></g>
  <g><rect x="320" y="220" width="110" height="80" fill="url(#g3)"/><text x="375" y="262" font-size="12" font-weight="700" text-anchor="middle" fill="#fff">湖北</text><text x="375" y="280" font-size="10" text-anchor="middle" fill="#fff">¥12M/月</text></g>
  <g><rect x="220" y="240" width="110" height="80" fill="url(#g4)"/><text x="275" y="282" font-size="12" font-weight="700" text-anchor="middle" fill="#fff">陕西</text><text x="275" y="300" font-size="10" text-anchor="middle" fill="#fff">¥9M/月</text></g>

  <!-- Legend -->
  <g transform="translate(40,420)">
    <text font-size="11" fill="#cbd5e1" font-weight="600">销量规模</text>
    <rect x="80" y="-8" width="16" height="12" fill="url(#g1)"/>
    <text x="100" y="2" font-size="10" fill="#94a3b8">≥ 20M</text>
    <rect x="140" y="-8" width="16" height="12" fill="url(#g2)"/>
    <text x="160" y="2" font-size="10" fill="#94a3b8">10-20M</text>
    <rect x="210" y="-8" width="16" height="12" fill="url(#g3)"/>
    <text x="230" y="2" font-size="10" fill="#94a3b8">5-10M</text>
    <rect x="280" y="-8" width="16" height="12" fill="url(#g4)"/>
    <text x="300" y="2" font-size="10" fill="#94a3b8">&lt; 5M</text>
  </g>
  <text x="400" y="470" font-size="10" text-anchor="middle" fill="#64748b">数据来源：RAG 检索 demo_cache · 演示数据</text>
</svg>`;
fs.writeFileSync(path.join(OUT, 'china-sales-heatmap.svg'), chinaSvg);

// 5-8. Risk 4 张防伪对比图
function makeGuideSvg(title, realLabel, fakeLabel, realColor, fakeColor, defects) {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 400" font-family="ui-sans-serif, system-ui, sans-serif">
  <defs>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="2" stdDeviation="3" flood-opacity="0.15"/>
    </filter>
  </defs>
  <rect width="600" height="400" fill="#f9fafb"/>
  <text x="300" y="28" font-size="16" font-weight="700" text-anchor="middle" fill="#111827">${title}</text>

  <!-- 正品 -->
  <g transform="translate(40,60)">
    <rect width="220" height="280" rx="10" fill="${realColor}" filter="url(#shadow)"/>
    <text x="110" y="30" font-size="13" font-weight="700" text-anchor="middle" fill="#fff">✓ ${realLabel}</text>
    <text x="110" y="60" font-size="9" text-anchor="middle" fill="#fff" opacity="0.9">正品特征</text>
    ${defects.real.map((d, i) => `<g transform="translate(20,${85 + i*30})">
      <circle r="3" fill="#fff"/>
      <text x="14" y="4" font-size="9" fill="#fff">${d}</text>
    </g>`).join('')}
  </g>

  <!-- 假货 -->
  <g transform="translate(340,60)">
    <rect width="220" height="280" rx="10" fill="${fakeColor}" filter="url(#shadow)"/>
    <text x="110" y="30" font-size="13" font-weight="700" text-anchor="middle" fill="#fff">✗ ${fakeLabel}</text>
    <text x="110" y="60" font-size="9" text-anchor="middle" fill="#fff" opacity="0.9">假货特征</text>
    ${defects.fake.map((d, i) => `<g transform="translate(20,${85 + i*30})">
      <circle r="3" fill="#fbbf24"/>
      <text x="14" y="4" font-size="9" fill="#fff">${d}</text>
    </g>`).join('')}
  </g>

  <text x="300" y="380" font-size="10" text-anchor="middle" fill="#6b7280">对比要点请扫描官方防伪码二次确认</text>
</svg>`;
}

fs.writeFileSync(path.join(OUT, 'anti-counterfeit-1.svg'),
  makeGuideSvg('包装盒对比', '正品包装', '假货包装', '#059669', '#dc2626', {
    real: ['盒体厚实，0.6mm 灰板', '印刷清晰，色差 ΔE&lt;2', '封口均匀，无胶痕', '防伪码激光刻印'],
    fake: ['盒体偏薄，&lt;0.4mm 灰板', '印刷模糊，色差 ΔE&gt;5', '封口有溢胶/重压痕', '防伪码普通油墨印']
  }));

fs.writeFileSync(path.join(OUT, 'anti-counterfeit-2.svg'),
  makeGuideSvg('防伪码位置', '正品防伪码', '假货防伪码', '#2563eb', '#7c2d12', {
    real: ['盒盖内侧激光刻码', '银色金属光泽，斜视可见', '扫码进入官方验证', '每码仅一次有效'],
    fake: ['外盒印刷普通', '黑色油墨，无光泽', '扫码跳第三方钓鱼站', '可重复使用/批量复制']
  }));

fs.writeFileSync(path.join(OUT, 'anti-counterfeit-3.svg'),
  makeGuideSvg('产品细节', '正品工艺', '假货工艺', '#7c3aed', '#b91c1c', {
    real: ['漆面均匀，3 层 UV 漆', '关节阻尼适中，3 年质保', '眼睛印刷 2400dpi', '底座 LOGO 凸版压印'],
    fake: ['漆面单层，易掉色', '关节过紧/过松，无阻尼', '眼睛印刷 600dpi 模糊', '底座 LOGO 贴纸粘贴']
  }));

fs.writeFileSync(path.join(OUT, 'anti-counterfeit-4.svg'),
  makeGuideSvg('官方授权渠道', '正品渠道', '假货渠道', '#0ea5e9', '#ea580c', {
    real: ['泡泡玛特天猫旗舰店', '京东自营官方店', '线下门店/快闪店', '抽盒机官方小程序'],
    fake: ['未授权 C 店 / 拼多多', '闲鱼低于 6 折新链接', '微商朋友圈 / 二级代理', '海外免税店非授权版']
  }));

console.log('Generated 8 SVG assets:');
['arch-system', 'arch-detail', 'reasoning-flow', 'china-sales-heatmap',
 'anti-counterfeit-1', 'anti-counterfeit-2', 'anti-counterfeit-3', 'anti-counterfeit-4'
].forEach(n => {
  const stat = fs.statSync(path.join(OUT, n + '.svg'));
  console.log(`  ${n}.svg (${(stat.size/1024).toFixed(1)}KB)`);
});
