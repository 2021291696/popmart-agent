// e2e fixtures：按后端新契约 mock（jobs REST + SSE、visualize、scenarios、history、本地演示副本）
// 旧契约（/api/analyze、三层降级 cache.json entries）已废弃，相关 mock 一并重写
import { test as base, expect } from '@playwright/test'

export const MOCK_JOB_ID = 'job-mock-1'
export const DEMO_QUERY = '泡泡玛特最近的市场表现如何？'
export const SUPPLY_QUERY = 'LABUBU 为什么能成为泡泡玛特的核心IP？'
export const RISK_QUERY = '泡泡玛特消费者投诉和二手假货风险有多高？'

export const MOCK_EXECUTIVE = {
  query: DEMO_QUERY,
  title: '泡泡玛特综合分析',
  total_agents: 2,
  total_steps: 4,
  total_llm_calls: 6,
  elapsed_seconds: 45.3,
  generated_at: '2026-07-13 14:30',
  final_answer: '综合分析：LABUBU 热度持续上升，复购率提升至 68%。',
  agents: [
    {
      name: 'ip_intelligence',
      conclusion: 'LABUBU 在社交媒体热度持续上升...',
      steps: 2,
      llm_calls: 3,
      sources_count: 5,
    },
    {
      name: 'consumer_insights',
      conclusion: '消费者复购率从 55% 提升至 68%...',
      steps: 2,
      llm_calls: 3,
      sources_count: 3,
    },
  ],
}

export const MOCK_SUPPLY = {
  query: SUPPLY_QUERY,
  title: 'LABUBU IP 深度分析',
  generated_at: '2026-07-13 14:30',
  final_answer: 'LABUBU 成功源于稀缺性营销 + 跨界联名 + 设计师龙家升',
  agent: {
    name: 'ip_intelligence',
    query: '查 LABUBU',
    final_answer: 'LABUBU 成功源于稀缺性营销 + 跨界联名 + 设计师龙家升',
    total_steps: 3,
    llm_calls: 4,
    steps: [
      { step: 1, thought: '需要查询 LABUBU 热度数据', action: 'web_search', action_input: 'LABUBU', result: '找到 15 条相关讨论' },
      { step: 2, thought: '需要分析这些内容的情感倾向', action: 'sentiment_analyze', action_input: '[...]', result: '正面 78%' },
      { step: 3, thought: '与 MOLLY 对比', action: 'trend_compare', action_input: 'LABUBU,MOLLY', result: 'LABUBU 提及量高 60%' },
    ],
    tool_stats: { web_search: { calls: 1 }, sentiment_analyze: { calls: 1 }, trend_compare: { calls: 1 } },
  },
  tool_distribution: [
    { name: 'web_search', calls: 1 },
    { name: 'sentiment_analyze', calls: 1 },
    { name: 'trend_compare', calls: 1 },
  ],
}

export const MOCK_RISK_WITH_CONFLICT = {
  query: RISK_QUERY,
  title: '消费者风险分析',
  generated_at: '2026-07-13 14:30',
  final_answer: '整体投诉下降，但假货风险上升。需区分产品质量投诉与渠道假货投诉。',
  total_rounds: 2,
  has_conflict: true,
  conflicts: [
    {
      agent_a: 'consumer_insights',
      agent_b: 'anti_counterfeit',
      claim_a: '整体投诉量下降 15%',
      claim_b: '假货举报上升 23%',
      reason: '不同维度：质量投诉 vs 渠道假货',
    },
  ],
  agents: [
    { name: 'consumer_insights', final_answer: '整体投诉量下降 15%', steps: 2, llm_calls: 2, sources_count: 3 },
    { name: 'anti_counterfeit', final_answer: '假货举报上升 23%', steps: 2, llm_calls: 2, sources_count: 4 },
  ],
}

export const MOCK_RISK_NO_CONFLICT = {
  ...MOCK_RISK_WITH_CONFLICT,
  has_conflict: false,
  conflicts: [],
  total_rounds: 1,
  final_answer: '无冲突：消费者投诉和假货风险均处于低位，无需特别干预。',
}

export const MOCK_SCENARIOS = {
  scenarios: [
    { id: 'market', label: '综合市场表现', query: DEMO_QUERY, page: 'executive', cached: true },
    { id: 'labubu', label: 'LABUBU IP 解析', query: SUPPLY_QUERY, page: 'supply', cached: true },
    { id: 'risk', label: '消费者风险', query: RISK_QUERY, page: 'risk', cached: false },
  ],
  count: 3,
}

export const MOCK_HISTORY = {
  items: [
    {
      query: DEMO_QUERY,
      saved_at: '2026-07-14 12:00',
      total_agents: 2,
      elapsed_seconds: 45.2,
      snippet: '核心结论：增长强劲',
      recommended_page: 'executive',
    },
    {
      query: SUPPLY_QUERY,
      saved_at: '2026-07-14 11:00',
      total_agents: 1,
      elapsed_seconds: 30.0,
      snippet: 'LABUBU 热度上升',
      recommended_page: 'supply',
    },
  ],
  count: 2,
}

// Job REST 响应工厂（新契约：status 终态为 completed/failed）
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
// 注意：playwright fulfill 的 SSE 是一次性给完 body 后断流，前端收到 complete 帧即关闭连接；
// 若断流先于结束帧，useJob 会自动降级为 REST 轮询——两条路径都被覆盖到。
export async function mockApiRoutes(page, options = {}) {
  const { job = mockJob(), events = DEFAULT_SSE_FRAMES } = options

  await page.route(/\/api\/visualize\/executive/, (route) =>
    route.fulfill({ json: MOCK_EXECUTIVE, status: 200 })
  )
  await page.route(/\/api\/visualize\/supply/, (route) =>
    route.fulfill({ json: MOCK_SUPPLY, status: 200 })
  )
  await page.route(/\/api\/visualize\/risk/, (route) =>
    route.fulfill({ json: MOCK_RISK_WITH_CONFLICT, status: 200 })
  )
  await page.route(/\/api\/scenarios/, (route) =>
    route.fulfill({ json: MOCK_SCENARIOS, status: 200 })
  )
  await page.route(/\/api\/history/, (route) =>
    route.fulfill({ json: MOCK_HISTORY, status: 200 })
  )
  // 本地演示副本默认 404：降级未命中 → 看板显示错误卡（命中场景由 spec 显式覆盖）
  await page.route(/\/data\/cache\.json/, (route) =>
    route.fulfill({ status: 404, body: 'not mocked' })
  )
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

// 扩展 test fixture：默认拦截全部后端 API，让 e2e 不依赖真实后端（后端正在并行改造）
export const test = base.extend({
  page: async ({ page }, use) => {
    await mockApiRoutes(page)
    await use(page)
  },
})

export { expect }
