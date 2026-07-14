// 404 页面 - 兜底路由，避免访问 /xxx 显示空白
import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div className="not-found">
      <div className="container">
        <h1>404</h1>
        <p>页面不存在</p>
        <Link to="/" className="btn-primary">返回首页</Link>
      </div>
    </div>
  )
}
