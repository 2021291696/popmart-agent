// 演示/降级数据 - 静态版本，面试时备用
// _source 字段标明数据来源，便于面试官追问时回答"这是 mock，真实数据走 API"

export const demoMetrics = [
  { _source: 'mock', label: '本周市场热度', value: 89, unit: '/100', change: '+12%', changeType: 'positive' },
  { _source: 'mock', label: '核心 IP 销量', value: 2.4, unit: '万件', change: '+18%', changeType: 'positive' },
  { _source: 'mock', label: '消费者投诉率', value: 0.3, unit: '%', change: '持平', changeType: 'neutral' },
  { _source: 'mock', label: '二手市场溢价', value: 185, unit: '%', change: '+22%', changeType: 'positive' },
]

export const demoTrendData = [
  { date: '07-01', mentions: 1200 },
  { date: '07-05', mentions: 1680 },
  { date: '07-10', mentions: 2340 },
  { date: '07-12', mentions: 2890 },
]

export const demoSupplyPlan = {
  _source: 'mock',
  total: 3300,
  cost: 29.4,
  revenue: 51.5,
  items: [
    { name: '精灵款', ratio: 0.36, count: 1200, reason: '热度持续攀升，二手溢价率 235%' },
    { name: '小恶魔款', ratio: 0.30, count: 1000, reason: '社交媒体讨论度高' },
    { name: '经典款', ratio: 0.18, count: 600, reason: '稳定走货款' },
    { name: '其他款式', ratio: 0.16, count: 500, reason: '满足多样化需求' },
  ],
}

export const demoSalesTrend = [
  { date: '07-01', sales: 650 },
  { date: '07-05', sales: 720 },
  { date: '07-10', sales: 890 },
  { date: '07-12', sales: 1050 },
]

export const demoRiskTrend = [
  { date: '07-01', 假货: 98, 物流: 72, 质量: 45 },
  { date: '07-05', 假货: 105, 物流: 81, 质量: 38 },
  { date: '07-10', 假货: 127, 物流: 89, 质量: 34 },
  { date: '07-12', 假货: 132, 物流: 95, 质量: 29 },
]

export const demoComplaintTypes = [
  { name: '发货慢', value: 64 },
  { name: '包装破损', value: 28 },
  { name: '质量异议', value: 8 },
]
