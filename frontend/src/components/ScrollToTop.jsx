// 路由切换时滚动到顶部 - SPA 常见问题，否则用户进入子页时仍停留在旧滚动位置
import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'

export default function ScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])
  return null
}
