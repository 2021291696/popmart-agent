// 全局演示数据提示横幅 - 让面试官一眼看清数据来源，避免被问"数据是真的吗"
import { Info } from 'lucide-react'

export default function DemoBanner() {
  return (
    <div className="demo-banner">
      <Info size={18} />
      <span>当前展示演示数据，用于面试场景展示</span>
    </div>
  )
}
