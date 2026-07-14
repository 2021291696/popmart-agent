// 饼图 - 风险/投诉比例展示用
import { PieChart as RePieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts'

const COLORS = ['#3C5A78', '#FF6B9D', '#F59E0B', '#10B981', '#EF4444']

export default function PieChart({ data, nameKey = 'name', valueKey = 'value', height = 300 }) {
  return (
    <div className="chart-container" style={{ width: '100%', height }}>
      <ResponsiveContainer width="100%" height="100%">
        <RePieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            outerRadius={100}
            dataKey={valueKey}
            nameKey={nameKey}
            label={(entry) => `${entry[nameKey]}: ${entry[valueKey]}`}
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip />
          <Legend />
        </RePieChart>
      </ResponsiveContainer>
    </div>
  )
}
