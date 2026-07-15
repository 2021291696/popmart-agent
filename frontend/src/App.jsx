// 应用布局壳 - 统一管理 Nav/Footer，子页面只关心内容
import { Outlet, useLocation } from 'react-router-dom'
import Nav from './components/Nav'
import Footer from './components/Footer'

export default function App() {
  const location = useLocation()
  // /chat 是应用式固定布局（chat-lock 锁滚动），页面版 Footer 在此会破坏布局，不渲染
  const hideFooter = location.pathname === '/chat'
  return (
    <div className="app">
      <Nav />
      <main>
        <Outlet />
      </main>
      {!hideFooter && <Footer />}
    </div>
  )
}
