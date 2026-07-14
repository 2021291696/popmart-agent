// 应用布局壳 - 统一管理 Nav/Footer，子页面只关心内容
import { Outlet } from 'react-router-dom'
import Nav from './components/Nav'
import Footer from './components/Footer'

export default function App() {
  return (
    <div className="app">
      <Nav />
      <main>
        <Outlet />
      </main>
      <Footer />
    </div>
  )
}
