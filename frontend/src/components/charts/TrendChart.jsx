// 折线趋势图 - 复用组件，Executive/Supply/Risk 三页都用到
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Area
} from 'recharts'

export default function TrendChart({ data, xKey = 'date', lines, height = 300 }) {
  // lines: [{ key, color, label }] —— 多线支持
  return (
    <div className="chart-container" style={{ width: '100%', height }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#E7E3DA" />
          <XAxis dataKey={xKey} tick={{ fontSize: 12, fill: '#6B7077' }} />
          <YAxis tick={{ fontSize: 12, fill: '#6B7077' }} />
          <Tooltip
            contentStyle={{ background: '#fff', border: '1px solid #E7E3DA', borderRadius: 6, fontSize: 13 }}
          />
          {lines.map((line) => (
            <Area
              key={`area-${line.key}`}
              type="monotone"
              dataKey={line.key}
              stroke={line.color}
              fill={line.color}
              fillOpacity={0.08}
              legendType="none"
            />
          ))}
          {lines.map((line) => (
            <Line
              key={`line-${line.key}`}
              type="monotone"
              dataKey={line.key}
              stroke={line.color}
              strokeWidth={2}
              dot={false}
              name={line.label || line.key}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
