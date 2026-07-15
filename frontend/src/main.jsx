// 应用入口 - 装配 Router + ErrorBoundary + ScrollToTop + Lazy Loading
import React, { Suspense, lazy } from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import './index.css'
import App from './App'
import ErrorBoundary from './components/ErrorBoundary'
import ScrollToTop from './components/ScrollToTop'
import Loading from './components/Loading'

// 路由级 code splitting - 首屏只加载 Landing，按需加载其他页面
const Landing = lazy(() => import('./pages/Landing'))
const Executive = lazy(() => import('./pages/Executive'))
const Supply = lazy(() => import('./pages/Supply'))
const Risk = lazy(() => import('./pages/Risk'))
const Chat = lazy(() => import('./pages/Chat'))
const Data = lazy(() => import('./pages/Data'))
const AnalysisProgress = lazy(() => import('./pages/AnalysisProgress'))
const NotFound = lazy(() => import('./pages/NotFound'))

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <ScrollToTop />
      <ErrorBoundary>
        <Suspense fallback={<Loading />}>
          <Routes>
            <Route path="/" element={<App />}>
              <Route index element={<Landing />} />
              <Route path="chat" element={<Chat />} />
              <Route path="data" element={<Data />} />
              <Route path="progress/:jobId" element={<AnalysisProgress />} />
              <Route path="executive" element={<Executive />} />
              <Route path="supply" element={<Supply />} />
              <Route path="risk" element={<Risk />} />
              <Route path="*" element={<NotFound />} />
            </Route>
          </Routes>
        </Suspense>
      </ErrorBoundary>
    </BrowserRouter>
  </React.StrictMode>,
)
