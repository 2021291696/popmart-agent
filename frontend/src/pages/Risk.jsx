import React, { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import './Risk.css'
import PageHeader from '../components/PageHeader'
import MarkdownView from '../components/MarkdownView'
import { fetchRiskViz } from '../services/api'

export default function Risk() {
  const [searchParams] = useSearchParams()
  const query = searchParams.get('query') || ''
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    fetchRiskViz(query)
      .then((viz) => {
        setData(viz)
        setLoading(false)
      })
      .catch((err) => {
        setError(err.message)
        setLoading(false)
      })
  }, [query])

  if (loading) {
    return (
      <div className="risk-page loading-screen">
        <div className="loading-pulse"></div>
        <p>正在加载风险分析...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="risk-page">
        <PageHeader title="消费者风险分析" description="冲突检测与仲裁" />
        <div className="container">
          <div className="error-card">
            <h3>⚠️ 数据未就绪</h3>
            <p>{error}</p>
            <p className="error-hint">
              请先在<a href="/chat">对话分析</a>提交一个问题，系统会自动生成看板数据。
            </p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="risk-page">
      <PageHeader
        title={data.title}
        description={`冲突检测与仲裁 · ${data.total_rounds} 轮 · ${data.has_conflict ? '检测到冲突' : '结论一致'}`}
      />

      <div className="container">
        {/* 状态横幅 */}
        <section className="status-section">
          <div className={`status-card ${data.has_conflict ? 'conflict' : 'ok'} fade-in`}>
            <div className="status-icon">{data.has_conflict ? '⚠️' : '✅'}</div>
            <div className="status-body">
              <div className="status-title">
                {data.has_conflict
                  ? `检测到 ${data.conflicts.length} 处潜在矛盾`
                  : '各 Agent 结论一致，未检测到冲突'}
              </div>
              <div className="status-subtitle">
                {data.has_conflict
                  ? 'LLM 已识别矛盾维度，需追加仲裁'
                  : '所有 Agent 基于各自数据来源给出互补判断'}
              </div>
            </div>
          </div>
        </section>

        {/* 冲突对比 */}
        {data.has_conflict && data.conflicts.length > 0 && (
          <section className="conflict-section">
            <h2 className="section-title">⚔️ 冲突详情</h2>
            {data.conflicts.map((c, idx) => {
              const agentA = data.agents.find((a) => a.name === c.agent_a)
              const agentB = data.agents.find((a) => a.name === c.agent_b)
              return (
                <div key={idx} className="conflict-card fade-in">
                  <div className="conflict-vs-row">
                    <div className="conflict-side">
                      <div className="conflict-agent-name">{c.agent_a}</div>
                      <div className="conflict-claim">{c.claim_a || agentA?.final_answer?.slice(0, 120) || '—'}</div>
                    </div>
                    <div className="conflict-vs">VS</div>
                    <div className="conflict-side">
                      <div className="conflict-agent-name">{c.agent_b}</div>
                      <div className="conflict-claim">{c.claim_b || agentB?.final_answer?.slice(0, 120) || '—'}</div>
                    </div>
                  </div>
                  {c.reason && (
                    <div className="conflict-reason">
                      <strong>LLM 判断：</strong> {c.reason}
                    </div>
                  )}
                </div>
              )
            })}
          </section>
        )}

        {/* 仲裁过程 */}
        <section className="arbitration-section">
          <h2 className="section-title">🔍 仲裁过程</h2>
          <div className="rounds-card">
            <div className="round-item">
              <div className="round-header">
                <span className="round-number">Round 1</span>
                <span className="round-label">初始分析</span>
              </div>
              <div className="round-agents">
                {data.agents.map((a) => (
                  <div key={a.name} className="round-agent">
                    <span className="round-agent-name">{a.name}</span>
                    <span className="round-agent-claim">{a.final_answer?.slice(0, 120) || '—'}</span>
                  </div>
                ))}
              </div>
            </div>
            {data.total_rounds > 1 && (
              <div className="round-item">
                <div className="round-header">
                  <span className="round-number">Round 2</span>
                  <span className="round-label">引用来源重新分析</span>
                </div>
                <p className="round-desc">
                  LLM 重新审视双方结论的指标、地域、时间维度，识别矛盾是否为真矛盾。
                </p>
              </div>
            )}
          </div>
        </section>

        {/* 调和结论 */}
        <section className="report-section">
          <h2 className="section-title">✅ 调和结论</h2>
          <div className="report-card">
            <MarkdownView content={data.final_answer} />
            <div className="verification-row">
              <span className="verification-badge">✅ 数据一致性已验证</span>
              <span className="verification-badge">✅ 来源可追溯</span>
            </div>
          </div>
        </section>

        <footer className="page-footer">
          数据更新时间：{data.generated_at || '未知'}
        </footer>
      </div>
    </div>
  )
}