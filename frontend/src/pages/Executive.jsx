import React, { useEffect, useState } from 'react'
import './Executive.css'
import PageHeader from '../components/PageHeader'
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

  if (loading) return <div className="executive-page"><PageHeader title="加载中..." /></div>
  if (error) return (
    <div className="executive-page">
      <PageHeader title="老板早会页" description="多 Agent 协作全景" />
      <div className="error-banner">
        <h3>⚠️ 数据未就绪</h3>
        <p>{error}</p>
        <p>请先在 Streamlit 主入口（http://localhost:8501）跑一次分析，预热缓存。</p>
      </div>
    </div>
  )

  if (!data) return null

  return (
    <div className="executive-page" data-source="visualize-api">
      <PageHeader
        title={data.title || "泡泡玛特综合分析"}
        description={`多 Agent 协作全景 · ${data.total_agents} agents · ${data.total_llm_calls} LLM 调用 · ${data.elapsed_seconds}s`}
      />

      {/* 顶部关键指标 */}
      <section className="metrics">
        <div className="container">
          <div className="metrics-grid">
            <div className="metric-card">
              <div className="metric-label">参与 Agent</div>
              <div className="metric-value">{data.total_agents}</div>
              <div className="metric-change neutral">个专业 Agent</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">推理步数</div>
              <div className="metric-value">{data.total_steps}</div>
              <div className="metric-change neutral">步</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">LLM 调用</div>
              <div className="metric-value">{data.total_llm_calls}</div>
              <div className="metric-change neutral">次</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">总耗时</div>
              <div className="metric-value">{data.elapsed_seconds}<span className="metric-unit">s</span></div>
              <div className="metric-change neutral">秒</div>
            </div>
          </div>
        </div>
      </section>

      {/* 核心结论 */}
      <section className="final-answer">
        <div className="container">
          <h2>📋 综合报告</h2>
          <div className="markdown-content">
            <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit' }}>{data.final_answer}</pre>
          </div>
        </div>
      </section>

      {/* 各 Agent 结论卡片 */}
      <section className="agent-cards">
        <div className="container">
          <h2>🤖 各 Agent 调研结论</h2>
          <div className="agent-grid">
            {data.agents.map((agent) => (
              <div key={agent.name} className="agent-card">
                <div className="agent-header">
                  <span className="agent-name">{agent.name}</span>
                  <span className="agent-stats">{agent.steps} 步 · {agent.llm_calls} 调用</span>
                </div>
                <p className="agent-conclusion">{agent.conclusion}</p>
                <div className="agent-meta">📊 {agent.sources_count} 次数据调用</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 数据更新时间 */}
      <section className="meta-footer">
        <div className="container">
          <p className="meta-text">数据更新时间：{data.generated_at || "未知"}</p>
        </div>
      </section>
    </div>
  )
}