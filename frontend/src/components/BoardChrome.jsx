// 三看板共享的页头工具条与空态组件 - 避免 Executive/Supply/Risk 各自重复
import React from 'react'

// 页头下方工具条：左侧显示该看板的固定分析目标，右侧「刷新分析」按钮
export function BoardToolbar({ query, onRefresh, refreshing, refreshError }) {
  return (
    <div className="board-toolbar">
      <span className="board-toolbar-meta" title={query}>
        分析目标：{query}
      </span>
      <button className="btn-primary board-refresh-btn" onClick={onRefresh} disabled={refreshing}>
        {refreshing ? '正在创建任务…' : '刷新分析'}
      </button>
      {refreshError && <div className="board-toolbar-error">{refreshError}</div>}
    </div>
  )
}

// 404 空态：该看板从未分析过，引导用户点击刷新生成
export function BoardEmptyState({ onRefresh, refreshing, refreshError }) {
  return (
    <div className="board-empty fade-in">
      <div className="board-empty-icon">🗂️</div>
      <h3>该看板尚无分析结果</h3>
      <p>点击下方按钮，Multi-Agent 将立即为该看板生成专属分析</p>
      <button className="btn-primary board-empty-btn" onClick={onRefresh} disabled={refreshing}>
        {refreshing ? '正在创建任务…' : '点击刷新分析生成'}
      </button>
      {refreshError && <div className="board-toolbar-error">{refreshError}</div>}
    </div>
  )
}
