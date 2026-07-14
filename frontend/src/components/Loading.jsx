// 全局 Loading 组件 - lazy 加载与数据请求时复用
import { Loader2 } from 'lucide-react'

export default function Loading() {
  return (
    <div className="loading">
      <Loader2 className="loading-icon" size={48} />
      <p>加载中...</p>
    </div>
  )
}
