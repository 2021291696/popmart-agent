// 演示数据提示横幅 - 看板降级到本地副本时显示，让面试官一眼看清数据来源
import { Info } from 'lucide-react'

export default function DemoBanner({ message = '离线演示数据 · 后端未连接' }) {
  return (
    <div className="demo-banner">
      <Info size={18} />
      <span>{message}</span>
    </div>
  )
}
