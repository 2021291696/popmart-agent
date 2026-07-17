// e2e fixtures：按数据中心化架构新契约 mock
// （boards / chat / data / jobs REST+SSE / scenarios）
// 旧契约（/api/visualize/*、/api/history、本地演示副本 cache.json）已随前端改造废弃
import { test as base, expect } from '@playwright/test'

export const MOCK_JOB_ID = 'job-mock-1'
export const DEMO_QUERY = '泡泡玛特最近的市场表现如何？'
export const SUPPLY_QUERY = 'LABUBU 为什么能成为泡泡玛特的核心IP？'
export const RISK_QUERY = '泡泡玛特消费者投诉和二手假货风险有多高？'

// ============================================================
// 看板 mock：GET /api/boards/{page} 的原始形态
// agents 是编排原始 sub_tasks（agent_name + result.steps/tool_stats/llm_calls/final_answer），
// 前端 normalizeBoardData 在客户端归一化成视图结构（与后端 _extract_viz_data 对齐）
// ============================================================

const EXEC_SUB_TASKS = [
  {
    task_id: 't-exec-1',
    agent_name: 'ip_intelligence',
    query: '评估核心 IP 热度',
    status: 'completed',
    result: {
      final_answer: 'LABUBU 在社交媒体热度持续上升...',
      steps: [
        { step: 1, thought: '查热度数据', action: 'web_search', action_input: 'LABUBU', result: '15 条相关讨论' },
        { step: 2, thought: '看趋势变化', action: 'trend_compare', action_input: 'LABUBU', result: '热度上升 30%' },
      ],
      tool_stats: { web_search: { calls: 3 }, trend_compare: { calls: 2 } },
      llm_calls: 3,
    },
  },
  {
    task_id: 't-exec-2',
    agent_name: 'consumer_insights',
    query: '分析消费者情绪',
    status: 'completed',
    result: {
      final_answer: '消费者复购率从 55% 提升至 68%...',
      steps: [
        { step: 1, thought: '查复购率', action: 'web_search', action_input: '复购率', result: '68%' },
        { step: 2, thought: '查论坛反馈', action: 'forum_scrape', action_input: '泡泡玛特', result: '正面 80%' },
      ],
      tool_stats: { web_search: { calls: 2 }, forum_scrape: { calls: 1 } },
      llm_calls: 3,
    },
  },
]

// ---- 看板 charts mock：后端 _extract_charts 预提取形态 ----
// agent_activity / ip_mentions（含诚实标注 note）/ sentiment{distribution, items}
const MOCK_CHARTS_EXECUTIVE = {
  agent_activity: [
    { name: 'ip_intelligence', steps: 4, llm_calls: 4, data_calls: 3 },
    { name: 'consumer_insights', steps: 3, llm_calls: 3, data_calls: 2 },
  ],
  ip_mentions: {
    time_range: '30d',
    note: '基于抓取语料的提及量,非真实时序指数。生产环境需接微博指数 API。',
    items: [
      { ip: 'LABUBU', mentions: 64, share_pct: 40.5 },
      { ip: 'MOLLY', mentions: 45, share_pct: 28.5 },
    ],
  },
  sentiment: {
    distribution: [
      { name: '正面', value: 1 },
      { name: '负面', value: 0 },
      { name: '中性', value: 8 },
    ],
    items: [
      { label: 'LABUBU 太可爱了', sentiment: '正面', intensity: 4, emotion: '喜悦' },
      { label: '抽盒体验一般', sentiment: '中性', intensity: 2, emotion: '' },
    ],
  },
}

export const MOCK_BOARD_EXECUTIVE = {
  page: 'executive',
  title: '老板早会',
  query: '综合评估泡泡玛特当前经营状况：市场表现、IP热度、消费者情绪与风险',
  saved_at: '2026-07-13 14:30',
  generated_at: '2026-07-13 14:30',
  final_answer: '综合分析：LABUBU 热度持续上升，复购率提升至 68%。',
  total_rounds: 1,
  result: { elapsed_seconds: 45.3, sub_tasks: EXEC_SUB_TASKS, conflicts: [] },
  agents: EXEC_SUB_TASKS,
  conflicts: [],
  charts: MOCK_CHARTS_EXECUTIVE,
}

const SUPPLY_SUB_TASKS = [
  {
    task_id: 't-supply-1',
    agent_name: 'ip_intelligence',
    query: '查 LABUBU',
    status: 'completed',
    result: {
      final_answer: 'LABUBU 成功源于稀缺性营销 + 跨界联名 + 设计师龙家升',
      steps: [
        { step: 1, thought: '需要查询 LABUBU 热度数据', action: 'web_search', action_input: 'LABUBU', result: '找到 15 条相关讨论' },
        { step: 2, thought: '需要分析这些内容的情感倾向', action: 'sentiment_analyze', action_input: '[...]', result: '正面 78%' },
        { step: 3, thought: '与 MOLLY 对比', action: 'trend_compare', action_input: 'LABUBU,MOLLY', result: 'LABUBU 提及量高 60%' },
      ],
      tool_stats: { web_search: { calls: 1 }, sentiment_analyze: { calls: 1 }, trend_compare: { calls: 1 } },
      llm_calls: 4,
    },
  },
]

export const MOCK_BOARD_SUPPLY = {
  page: 'supply',
  title: '备货分析',
  query: '分析泡泡玛特供应链与销量趋势，给出备货建议',
  saved_at: '2026-07-13 14:30',
  generated_at: '2026-07-13 14:30',
  final_answer: 'LABUBU 成功源于稀缺性营销 + 跨界联名 + 设计师龙家升',
  total_rounds: 1,
  result: { sub_tasks: SUPPLY_SUB_TASKS, conflicts: [] },
  agents: SUPPLY_SUB_TASKS,
  conflicts: [],
  charts: MOCK_CHARTS_EXECUTIVE, // 复用同形数据：supply 图区只渲染 ip_mentions + sentiment 三张卡
}

const RISK_SUB_TASKS = [
  {
    task_id: 't-risk-1',
    agent_name: 'consumer_insights',
    query: '分析投诉热点',
    status: 'completed',
    result: {
      final_answer: '整体投诉量下降 15%',
      steps: [
        { step: 1, thought: '查投诉数据', action: 'web_search', action_input: '投诉', result: '下降 15%' },
        { step: 2, thought: '归类投诉', action: 'forum_scrape', action_input: '投诉', result: '质量类为主' },
      ],
      tool_stats: { web_search: { calls: 2 }, forum_scrape: { calls: 1 } },
      llm_calls: 2,
    },
  },
  {
    task_id: 't-risk-2',
    agent_name: 'anti_counterfeit',
    query: '分析假货风险',
    status: 'completed',
    result: {
      final_answer: '假货举报上升 23%',
      steps: [
        { step: 1, thought: '查假货举报', action: 'web_search', action_input: '假货', result: '上升 23%' },
        { step: 2, thought: '核验渠道', action: 'image_check', action_input: '鉴定', result: '漏洞 2 处' },
      ],
      tool_stats: { web_search: { calls: 3 }, image_check: { calls: 1 } },
      llm_calls: 2,
    },
  },
]

export const MOCK_RISK_CONFLICT = {
  agent_a: 'consumer_insights',
  agent_b: 'anti_counterfeit',
  claim_a: '整体投诉量下降 15%',
  claim_b: '假货举报上升 23%',
  reason: '不同维度：质量投诉 vs 渠道假货',
}

// risk 客诉场景典型分布：负面为主、无 trend_compare（ip_mentions 为 null）
const MOCK_CHARTS_RISK = {
  agent_activity: [
    { name: 'consumer_insights', steps: 4, llm_calls: 4, data_calls: 3 },
    { name: 'anti_counterfeit', steps: 4, llm_calls: 4, data_calls: 3 },
  ],
  ip_mentions: null,
  sentiment: {
    distribution: [
      { name: '正面', value: 0 },
      { name: '负面', value: 7 },
      { name: '中性', value: 1 },
    ],
    items: [
      { label: '玩偶掉漆严重', sentiment: '负面', intensity: 5, emotion: '愤怒' },
      { label: '客服处理慢', sentiment: '负面', intensity: 4, emotion: '不满' },
      { label: '包装有破损', sentiment: '中性', intensity: 2, emotion: '' },
    ],
  },
}

export const MOCK_BOARD_RISK = {
  page: 'risk',
  title: '客诉应对',
  query: '排查泡泡玛特消费者投诉与二手假货风险',
  saved_at: '2026-07-13 14:30',
  generated_at: '2026-07-13 14:30',
  final_answer: '整体投诉下降，但假货风险上升。需区分产品质量投诉与渠道假货投诉。',
  total_rounds: 2,
  result: { sub_tasks: RISK_SUB_TASKS, conflicts: [MOCK_RISK_CONFLICT], total_rounds: 2 },
  agents: RISK_SUB_TASKS,
  conflicts: [MOCK_RISK_CONFLICT],
  charts: MOCK_CHARTS_RISK,
}

export const MOCK_BOARD_RISK_NO_CONFLICT = {
  ...MOCK_BOARD_RISK,
  conflicts: [],
  total_rounds: 1,
  final_answer: '无冲突：消费者投诉和假货风险均处于低位，无需特别干预。',
}

// 看板 404 空态响应体（后端原文）
export const BOARD_404_BODY = { detail: '该看板尚无分析结果，请点击「刷新分析」生成' }

// ============================================================
// 对话 mock：POST /api/chat + 会话列表/详情
// ============================================================

export const MOCK_CHAT_ANSWER = {
  session_id: 'sess-mock-1',
  answer: '根据资料，泡泡玛特核心 IP 包括 LABUBU、MOLLY、DIMOO。',
  sources: ['summarized_popmart_official_home_fact_5', 'summarized_popmart_wiki_baidu_fact_7'],
  confidence: 0.92,
  confidence_label: '确定（>90%）',
  query_type: 'fact',
  retrieved_chunks: 5,
}

export const MOCK_CHAT_SESSION = {
  id: 'sess-mock-1',
  title: '泡泡玛特的核心IP有哪些？',
  created_at: '2026-07-15T09:00:00+00:00',
  updated_at: '2026-07-15T09:05:00+00:00',
  message_count: 2,
}

export const MOCK_CHAT_SESSION_DETAIL = {
  id: MOCK_CHAT_SESSION.id,
  title: MOCK_CHAT_SESSION.title,
  created_at: MOCK_CHAT_SESSION.created_at,
  updated_at: MOCK_CHAT_SESSION.updated_at,
  messages: [
    { role: 'user', content: '泡泡玛特的核心IP有哪些？', ts: '2026-07-15T09:00:00+00:00' },
    {
      role: 'assistant',
      content: '核心 IP 包括 LABUBU、MOLLY、DIMOO。',
      sources: MOCK_CHAT_ANSWER.sources,
      confidence_label: '确定（>90%）',
      query_type: 'fact',
      ts: '2026-07-15T09:00:05+00:00',
    },
  ],
}

// ============================================================
// 数据页 mock：GET /api/data/overview
// 三个源覆盖 ok / never / http_N 三种抓取状态徽标
// ============================================================

export const MOCK_DATA_OVERVIEW = {
  sources: [
    {
      key: 'popmart_official_home',
      label: '泡泡玛特官网首页',
      url: 'https://www.popmart.com/cn',
      kind: 'official',
      scraped_at: '2026-07-15 09:00',
      scrape_status: 'ok',
      text_length: 1400,
      summarized: true,
      summary_preview: '泡泡玛特成立于2010年，是中国领先的潮流文化娱乐公司。',
      key_facts_count: 8,
    },
    {
      key: 'popmart_news',
      label: '行业新闻',
      url: 'https://example.com/news/popmart',
      kind: 'news',
      scraped_at: '',
      scrape_status: 'never',
      text_length: 0,
      summarized: false,
      summary_preview: '',
      key_facts_count: 0,
    },
    {
      key: 'popmart_forum',
      label: '玩家社区',
      url: 'https://example.com/forum/popmart',
      kind: 'social',
      scraped_at: '2026-07-15 09:01',
      scrape_status: 'http_502',
      text_length: 0,
      summarized: false,
      summary_preview: '',
      key_facts_count: 0,
    },
  ],
  last_scrape_attempt: { at: '2026-07-15 09:01', ok: 1, failed: 1 },
  summarized_at: '2026-07-15 09:05',
  summarized_model: 'deepseek-chat',
  vector_store: { active_collection: 'popmart_v3', chunks_total: 128 },
}

// ============================================================
// 场景（Landing）+ Job mock（与旧契约一致，jobs 体系未变）
// ============================================================

export const MOCK_SCENARIOS = {
  scenarios: [
    { id: 'market', label: '综合市场表现', query: DEMO_QUERY, page: 'executive', cached: true },
    { id: 'labubu', label: 'LABUBU IP 解析', query: SUPPLY_QUERY, page: 'supply', cached: true },
    { id: 'risk', label: '消费者风险', query: RISK_QUERY, page: 'risk', cached: false },
  ],
  count: 3,
}

// Job REST 响应工厂（status 终态为 completed/failed）
export function mockJob(overrides = {}) {
  return {
    id: MOCK_JOB_ID,
    query: DEMO_QUERY,
    status: 'completed',
    error: null,
    recommended_page: 'executive',
    created_at: '2026-07-14T10:00:00',
    updated_at: '2026-07-14T10:01:00',
    ...overrides,
  }
}

// 把 SSE 帧数组序列化为 text/event-stream body
export function sseBody(frames) {
  return frames.map((f) => `data: ${JSON.stringify(f)}\n\n`).join('')
}

export const DEFAULT_SSE_FRAMES = [
  { stage: 'decompose', message: '任务分解为 2 个子任务', payload: {}, timestamp: '2026-07-14T10:00:01' },
  { stage: 'agent_complete', message: 'ip_intelligence 完成', payload: {}, timestamp: '2026-07-14T10:00:30' },
  { stage: 'complete', message: '分析完成', payload: { recommended_page: 'executive' }, timestamp: '2026-07-14T10:01:00' },
]

// 通用路由装配。spec 内对同名端点再次 page.route 可覆盖默认值（playwright 后注册优先）。
// 看板 GET 默认 200 有缓存；404 空态与 500 错误由 spec 显式覆盖。
// 注意：playwright fulfill 的 SSE 是一次性给完 body 后断流，前端收到 complete 帧即关闭连接；
// 若断流先于结束帧，useJob 会自动降级为 REST 轮询——两条路径都被覆盖到。
export async function mockApiRoutes(page, options = {}) {
  const { job = mockJob(), events = DEFAULT_SSE_FRAMES } = options

  // ---- 三看板：GET 读缓存 / POST refresh 创建 job（$ 锚定避免互相误匹配） ----
  const boards = { executive: MOCK_BOARD_EXECUTIVE, supply: MOCK_BOARD_SUPPLY, risk: MOCK_BOARD_RISK }
  for (const [boardPage, data] of Object.entries(boards)) {
    await page.route(new RegExp(`/api/boards/${boardPage}$`), (route) => {
      if (route.request().method() === 'GET') route.fulfill({ json: data, status: 200 })
      else route.fallback()
    })
    await page.route(new RegExp(`/api/boards/${boardPage}/refresh$`), (route) => {
      if (route.request().method() === 'POST') {
        route.fulfill({ json: { job_id: MOCK_JOB_ID, status: 'pending', page: boardPage }, status: 200 })
      } else {
        route.fallback()
      }
    })
  }

  // ---- 对话：发消息 / 会话列表 / 会话详情 ----
  await page.route(/\/api\/chat$/, (route) => {
    if (route.request().method() === 'POST') route.fulfill({ json: MOCK_CHAT_ANSWER, status: 200 })
    else route.fallback()
  })
  await page.route(/\/api\/chat\/sessions$/, (route) =>
    route.fulfill({ json: { items: [MOCK_CHAT_SESSION] }, status: 200 })
  )
  await page.route(/\/api\/chat\/sessions\/[^/]+$/, (route) =>
    route.fulfill({ json: MOCK_CHAT_SESSION_DETAIL, status: 200 })
  )

  // ---- 数据页：总览 / 一键刷新 ----
  await page.route(/\/api\/data\/overview$/, (route) =>
    route.fulfill({ json: MOCK_DATA_OVERVIEW, status: 200 })
  )
  await page.route(/\/api\/data\/refresh$/, (route) => {
    if (route.request().method() === 'POST') {
      route.fulfill({ json: { job_id: MOCK_JOB_ID, status: 'pending' }, status: 200 })
    } else {
      route.fallback()
    }
  })

  // ---- Landing 场景 ----
  await page.route(/\/api\/scenarios/, (route) =>
    route.fulfill({ json: MOCK_SCENARIOS, status: 200 })
  )

  // ---- Job 体系：创建（旧 /api/jobs，供兼容性兜底）/ 查询 / SSE ----
  await page.route(/\/api\/jobs$/, (route) => {
    if (route.request().method() === 'POST') {
      route.fulfill({ json: { job_id: MOCK_JOB_ID, status: 'pending', query: DEMO_QUERY }, status: 200 })
    } else {
      route.fallback()
    }
  })
  await page.route(/\/api\/jobs\/[^/]+$/, (route) =>
    route.fulfill({ json: job, status: 200 })
  )
  await page.route(/\/api\/jobs\/[^/]+\/events$/, (route) =>
    route.fulfill({
      status: 200,
      headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' },
      body: sseBody(events),
    })
  )
}

// 扩展 test fixture：默认拦截全部后端 API，让 e2e 不依赖真实后端
export const test = base.extend({
  page: async ({ page }, use) => {
    await mockApiRoutes(page)
    await use(page)
  },
})

export { expect }
