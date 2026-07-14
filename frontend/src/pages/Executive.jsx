import React, { useEffect, useState } from 'react'
import './Executive.css'
import PageHeader from '../components/PageHeader'
import MarkdownView from '../components/MarkdownView'
import { fetchExecutiveViz } from '../services/api'

export default function Executive() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchExecutiveViz()
      .then((viz) => {
        setData(viz)
        setLoading(false)
      })
      .catch((err) => {
        setError(err.message)
        setLoading(false)
      })
  }, [])

  if (loading) {
    return (
      <div className="executive-page loading-screen">
        <div className="loading-pulse"></div>
        <p>正在加载综合分析...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="executive-page">
        <PageHeader title="泡泡玛特综合分析" description="多 Agent 协作全景" />
        <div className="container">
          <div className="error-card">
            <h3>⚠️ 数据未就绪</h3>
            <p>{error}</p>
            <p className="error-hint">请先在 Streamlit 主入口（http://localhost:8501）跑一次「综合市场表现」分析，预热缓存。</p>
          </div>
        </div>
      </div>
    )
  }

  if (!data) return null

  return (
    <div className="executive-page">
      <PageHeader
        title={data.title}
        description={`多 Agent 协作全景 · ${data.total_agents} 个专业 Agent · ${data.total_llm_calls} 次 LLM 调用 · ${data.elapsed_seconds}s`}
      />

      <div className="container">
        {/* 关键指标 */}
        <section className="metrics-row">
          {[
            { label: '参与 Agent', value: data.total_agents, unit: '个' },
            { label: '推理步数', value: data.total_steps, unit: '步' },
            { label: 'LLM 调用', value: data.total_llm_calls, unit: '次' },
            { label: '总耗时', value: data.elapsed_seconds, unit: 's' },
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
            {data.agents.map((agent, idx) => (
              <div key={agent.name} className="agent-card fade-in" style={{ animationDelay: `${(idx + 4) * 80}ms` }}>
                <div className="agent-card-header">
                  <span className="agent-name">{agent.name}</span>
                  <span className="agent-badge">{agent.steps} 步 · {agent.llm_calls} 调用</span>
                </div>
                <p className="agent-conclusion">{agent.conclusion}</p>
                <div className="agent-footer">
                  <span className="agent-sources">📊 {agent.sources_count} 次数据调用</span>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* 综合报告 */}
        <section className="report-section">
          <h2 className="section-title">📋 综合报告</h2>
          <div className="report-card fade-in">
            <MarkdownView content={data.final_answer} />
          </div>
        </section>

        <footer className="page-footer meta-text">
          数据更新时间：{data.generated_at || '未知'}
        </footer>
      </div>
    </div>
  )
}