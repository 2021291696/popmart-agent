// 页面标题 + 面包屑导航 - 三个子页面统一调用
import { Link } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'

export default function PageHeader({ title, description }) {
  return (
    <header className="page-header">
      <div className="container">
        <div className="breadcrumb">
          <Link to="/">首页</Link>
          <ChevronRight size={16} />
          <span>{title}</span>
        </div>
        <h1>{title}</h1>
        {description && <p className="page-description">{description}</p>}
      </div>
    </header>
  )
}
