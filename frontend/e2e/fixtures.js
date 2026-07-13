// e2e fixtures：mock FastAPI 返回的可视化数据
import { test as base, expect } from '@playwright/test'

// 真实后端会用 .demo_cache.json，这里 mock API 层让前端测试独立运行
export const MOCK_EXECUTIVE = {
  query: '泡泡玛特最近的市场表现如何？',
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
  query: 'LABUBU 为什么能成为泡泡玛特的核心IP？',
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
  query: '泡泡玛特消费者投诉和二手假货风险有多高？',
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
  final_answer: '消费者投诉和假货风险均处于低位，无需特别干预。',
}

// 扩展 test fixture：拦截 API 调用并返回 mock 数据
export const test = base.extend({
  page: async ({ page }, use) => {
    // 拦截所有 visualize API 调用（绝对 URL + glob）
    await page.route(/.*\/api\/visualize\/executive/, (route) =>
      route.fulfill({ json: MOCK_EXECUTIVE, status: 200 })
    )
    await page.route(/.*\/api\/visualize\/supply/, (route) =>
      route.fulfill({ json: MOCK_SUPPLY, status: 200 })
    )
    await page.route(/.*\/api\/visualize\/risk/, (route) =>
      route.fulfill({ json: MOCK_RISK_WITH_CONFLICT, status: 200 })
    )
    // 三层降级中可能调用的其他 API
    await page.route(/.*\/api\/scenarios/, (route) =>
      route.fulfill({ json: { scenarios: [], count: 0 }, status: 200 })
    )
    await page.route(/.*\/api\/analyze.*/, (route) =>
      route.fulfill({ json: { error: 'mocked' }, status: 404 })
    )
    await page.route(/.*\/data\/cache\.json/, (route) =>
      route.fulfill({ json: { entries: {} }, status: 200 })
    )
    await use(page)
  },
})

export { expect }