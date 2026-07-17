import React from 'react'
import {
  Bar,
  BarChart,
  Cell,
  LabelList,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import './BoardCharts.css'

// 与 index.css 主题变量同源的图表色板（recharts 需要具体色值，不能用 var()）
// isAnimationActive 全部关闭：看板是数据展示场景，且截图/验收要求确定性渲染
const COLORS = {
  primary: '#3C5A78',
  primaryLight: '#7A9BB8',
  sand: '#C9A96A',
  positive: '#5A9E6F',
  neutral: '#B0A99F',
  negative: '#D9534F',
  muted: '#6B7077',
}

const SENTIMENT_COLORS = {
  正面: COLORS.positive,
  中性: COLORS.neutral,
  负面: COLORS.negative,
}

const AXIS_TICK = { fill: COLORS.muted, fontSize: 12 }

const TOOLTIP_STYLE = {
  borderRadius: 6,
  border: '1px solid #E7E3DA',
  background: '#FFFFFF',
  fontSize: 13,
}

function ChartCard({ title, subtitle, note, children, height = 260 }) {
  return (
    <div className="chart-card fade-in">
      <div className="chart-card-header">
        <span className="chart-card-title">{title}</span>
        {subtitle && <span className="chart-card-subtitle">{subtitle}</span>}
      </div>
      <div className="chart-card-body" style={{ height }}>
        {children}
      </div>
      {note && <p className="chart-note">⚠️ {note}</p>}
    </div>
  )
}

// 每个 Agent 的推理步数 / LLM 调用 / 数据调用对比
export function AgentActivityChart({ data }) {
  if (!data || data.length === 0) return null
  return (
    <ChartCard title="Agent 工作量对比" subtitle="步数 / LLM 调用 / 数据调用">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
          <XAxis dataKey="name" tick={AXIS_TICK} tickLine={false} axisLine={{ stroke: '#E7E3DA' }} interval={0} />
          <YAxis tick={AXIS_TICK} tickLine={false} axisLine={false} allowDecimals={false} />
          <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: 'rgba(60, 90, 120, 0.06)' }} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Bar dataKey="steps" name="推理步数" fill={COLORS.primary} radius={[3, 3, 0, 0]} isAnimationActive={false} />
          <Bar dataKey="llm_calls" name="LLM 调用" fill={COLORS.primaryLight} radius={[3, 3, 0, 0]} isAnimationActive={false} />
          <Bar dataKey="data_calls" name="数据调用" fill={COLORS.sand} radius={[3, 3, 0, 0]} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}

// trend_compare 工具结果：各 IP 提及量与占比
export function IpMentionsChart({ data }) {
  if (!data || !data.items || data.items.length === 0) return null
  return (
    <ChartCard title="IP 热度提及量" subtitle={`${data.time_range || '近期'} · 语料提及次数与占比`} note={data.note}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data.items} layout="vertical" margin={{ top: 4, right: 56, left: 8, bottom: 4 }}>
          <XAxis type="number" hide />
          <YAxis
            type="category"
            dataKey="ip"
            width={100}
            tick={{ ...AXIS_TICK, fontSize: 13 }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            cursor={{ fill: 'rgba(60, 90, 120, 0.06)' }}
            formatter={(value, name, item) => [`${value} 次 · ${item.payload.share_pct}%`, '提及量']}
          />
          <Bar dataKey="mentions" fill={COLORS.primary} radius={[0, 3, 3, 0]} barSize={22} isAnimationActive={false}>
            <LabelList
              dataKey="share_pct"
              position="right"
              formatter={(v) => `${v}%`}
              style={{ fill: COLORS.muted, fontSize: 12 }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}

// sentiment_analyze 汇总：正面 / 中性 / 负面占比环形图
export function SentimentDonut({ sentiment }) {
  const dist = sentiment?.distribution?.filter((d) => d.value > 0) ?? []
  if (dist.length === 0) return null
  const total = dist.reduce((sum, d) => sum + d.value, 0)
  return (
    <ChartCard title="情感倾向分布" subtitle={`${total} 条语料样本`}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={dist}
            dataKey="value"
            nameKey="name"
            innerRadius="52%"
            outerRadius="78%"
            paddingAngle={2}
            strokeWidth={0}
            isAnimationActive={false}
          >
            {dist.map((entry) => (
              <Cell key={entry.name} fill={SENTIMENT_COLORS[entry.name] ?? COLORS.neutral} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            formatter={(value, name) => [`${value} 条（${Math.round((value / total) * 100)}%）`, name]}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
        </PieChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}

// sentiment_analyze 逐条：每条语料的情感强度（1-5），按情感着色
export function SentimentIntensityChart({ sentiment }) {
  const items = sentiment?.items ?? []
  if (items.length === 0) return null
  const height = Math.max(220, items.length * 40 + 24)
  return (
    <ChartCard title="逐条情感强度" subtitle="1 = 弱 · 5 = 强" height={height}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={items} layout="vertical" margin={{ top: 4, right: 40, left: 8, bottom: 4 }}>
          <XAxis type="number" domain={[0, 5]} hide />
          <YAxis
            type="category"
            dataKey="label"
            width={180}
            tick={{ ...AXIS_TICK, fontSize: 12 }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            cursor={{ fill: 'rgba(60, 90, 120, 0.06)' }}
            formatter={(value, name, item) => [
              `强度 ${value}/5 · ${item.payload.emotion || item.payload.sentiment}`,
              item.payload.sentiment,
            ]}
          />
          <Bar dataKey="intensity" radius={[0, 3, 3, 0]} barSize={16} isAnimationActive={false}>
            {items.map((entry, idx) => (
              <Cell key={idx} fill={SENTIMENT_COLORS[entry.sentiment] ?? COLORS.neutral} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}
