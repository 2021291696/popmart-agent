import React, { useState } from 'react'
import './Executive.css'
import PageHeader from '../components/PageHeader'
import MarkdownView from '../components/MarkdownView'
import { BoardEmptyState, BoardToolbar } from '../components/BoardChrome'
import { useBoard } from '../hooks/useBoard'

export default function Executive() {
  const { data, status, error, refresh } = useBoard('executive')
  const [refreshing, setRefreshing] = useState(false)
  const [refreshError, setRefreshError] = useState(null)

  const handleRefresh = async () => {
    setRefreshing(true)
    setRefreshError(null)
    const msg = await refresh()
    if (msg) setRefreshError(msg)
    setRefreshing(false)
  }

  if (status === 'loading') {
    return (
      <div className="executive-page loading-screen">
        <div className="loading-pulse"></div>
        <p>正在加载老板早会看板...</p>
      </div>
    )
  }

  if (status === 'empty') {
    return (
      <div className="executive-page">
        <PageHeader title="老板早会" description="多 Agent 协作全景" />
        <div className="container">
          <BoardEmptyState onRefresh={handleRefresh} refreshing={refreshing} refreshError={refreshError} />
        </div>
      </div>
    )
  }

  if (status === 'error') {
    return (
      <div className="executive-page">
        <PageHeader title="老板早会" description="多 Agent 协作全景" />
        <div className="container">
          <div className="error-card">
            <h3>⚠️ 看板加载失败</h3>
            <p>{error}</p>
            <p className="error-hint">可点击「刷新分析」重新生成，或稍后重试。</p>
          </div>
          <BoardToolbar query="" onRefresh={handleRefresh} refreshing={refreshing} refreshError={refreshError} />
        </div>
      </div>
    )
  }

  if (!data) return null

  return (
    <div className="executive-page">
      <PageHeader
        title={data.title}
        description={`多 Agent 协作全景 · ${data.total_agents ?? 0} 个专业 Agent · ${data.total_llm_calls ?? 0} 次 LLM 调用 · ${data.elapsed_seconds ?? 0}s`}
      />

      <div className="container">
        <BoardToolbar query={data.query} onRefresh={handleRefresh} refreshing={refreshing} refreshError={refreshError} />

        {/* 关键指标 */}
        <section className="metrics-row">
          {[
            { label: '参与 Agent', value: data.total_agents ?? 0, unit: '个' },
            { label: '推理步数', value: data.total_steps ?? 0, unit: '步' },
            { label: 'LLM 调用', value: data.total_llm_calls ?? 0, unit: '次' },
            { label: '总耗时', value: data.elapsed_seconds ?? 0, unit: 's' },
          ].map((m, idx) => (
            <div key={idx} className="metric-card fade-in" style={{ animationDelay: `${idx * 80}ms` }}>
              <div className="metric-label">{m.label}</div>
              <div className="metric-value">
                {m.value}
                <span className="metric-unit">{m.unit}</span>
              </div>
            </div>
          ))}
        </section>

        {/* Agent 贡献 */}
        <section className="agent-section">
          <h2 className="section-title">🤖 Agent 贡献</h2>
          <div className="agent-grid">
            {(data.agents ?? []).map((agent, idx) => (
              <div key={agent.name} className="agent-card fade-in" style={{ animationDelay: `${(idx + 4) * 80}ms` }}>
                <div className="agent-card-header">
                  <span className="agent-name">{agent.name}</span>
                  <span className="agent-badge">{agent.steps ?? 0} 步 · {agent.llm_calls ?? 0} 调用</span>
                </div>
                <p className="agent-conclusion">{agent.conclusion ?? ''}</p>
                <div className="agent-footer">
                  <span className="agent-sources">📊 {agent.sources_count ?? 0} 次数据调用</span>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* 综合报告 */}
        <section className="report-section">
          <h2 className="section-title">📋 综合报告</h2>
          <div className="report-card fade-in">
            <MarkdownView content={data.final_answer ?? ''} />
          </div>
        </section>

        <footer className="page-footer meta-text">
          数据更新时间：{data.generated_at || '未知'}
        </footer>
      </div>
    </div>
  )
}
