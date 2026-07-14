// 顶部导航组件 - 统一在 App.jsx 中调用，避免四个页面各自重复实现
import { Link, useLocation } from 'react-router-dom'
import { BarChart3, Menu, X } from 'lucide-react'
import { useState } from 'react'

export default function Nav() {
  const [open, setOpen] = useState(false)
  const location = useLocation()
  const links = [
    { path: '/', label: '首页' },
    { path: '/chat', label: '对话分析' },
    { path: '/history', label: '历史数据' },
    { path: '/executive', label: '老板早会' },
    { path: '/supply', label: '备货分析' },
    { path: '/risk', label: '客诉应对' },
  ]

  // 「对话分析」在 /chat 和分析进度页 /progress/* 都保持高亮
  const isActive = (path) => {
    if (path === '/chat') {
      return location.pathname === '/chat' || location.pathname.startsWith('/progress/')
    }
    return location.pathname === path
  }

  return (
    <nav className="nav">
      <div className="container">
        <div className="nav-content">
          <Link to="/" className="logo">
            <BarChart3 className="logo-icon" />
            <span className="logo-text">泡泡玛特 Agent 系统</span>
          </Link>
          <button className="nav-toggle" onClick={() => setOpen(!open)} aria-label="菜单">
            {open ? <X size={24} /> : <Menu size={24} />}
          </button>
          <div className={`nav-links ${open ? 'open' : ''}`}>
            {links.map(link => (
              <Link
                key={link.path}
                to={link.path}
                className={isActive(link.path) ? 'active' : ''}
                onClick={() => setOpen(false)}
              >
                {link.label}
              </Link>
            ))}
          </div>
        </div>
      </div>
    </nav>
  )
}
