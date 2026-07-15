// 错误边界 - 防止组件渲染异常导致整页白屏，面试演示时大忌
// 路由变化时自动 reset（否则整站砖化无出口），并提供「返回首页」按钮
import { Component } from 'react'
import { Link, useLocation } from 'react-router-dom'

class ErrorBoundaryInner extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    // ponytail: console 简版即可，生产环境应接入 Sentry/上报服务
    console.error('ErrorBoundary caught:', error, errorInfo)
  }

  componentDidUpdate(prevProps) {
    // 路由已切换 → 自动复位，让目标页面有机会正常渲染
    if (this.state.hasError && prevProps.locationKey !== this.props.locationKey) {
      this.setState({ hasError: false, error: null })
    }
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary">
          <h2>页面出错了</h2>
          <p>请刷新页面重试，或返回首页。</p>
          <pre>{this.state.error?.message}</pre>
          <Link to="/" className="btn-primary" onClick={this.handleReset}>
            返回首页
          </Link>
        </div>
      )
    }
    return this.props.children
  }
}

// 类组件无法直接用 hooks，包一层拿到 location 用于路由变化检测
export default function ErrorBoundary({ children }) {
  const location = useLocation()
  return <ErrorBoundaryInner locationKey={location.key}>{children}</ErrorBoundaryInner>
}
