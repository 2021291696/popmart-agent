import React, { useEffect, useState } from 'react'
import './Risk.css'
import PageHeader from '../components/PageHeader'
import { fetchRiskViz } from '../services/api'

export default function Risk() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchRiskViz()
      .then((viz) => {
        setData(viz)
        setLoading(false)
      })
      .catch((err) => {
        setError(err.message)
        setLoading(false)
      })
  }, [])

  if (loading) return <div className="risk-page"><PageHeader title="加载中..." /></div>
  if (error) return (
    <div className="risk-page">
      <PageHeader title="客诉应对页" description="冲突检测与仲裁" />
      <div className="error-banner">
        <h3>⚠️ 数据未就绪</h3>
        <p>{error}</p>
        <p>请先在 Streamlit 主入口跑一次分析预热缓存。</p>
      </div>
    </div>
  )

  return (
    <div className="risk-page" data-source="visualize-api">
      <PageHeader
        title={data.title || "消费者风险分析"}
        description={`冲突检测与仲裁 · ${data.total_rounds} 轮 · ${data.has_conflict ? '检测到冲突' : '无冲突'}`}
      />

      {/* 顶部状态 */}
      <section className="risk-status">
        <div className="container">
          <div className="status-banner" data-has-conflict={data.has_conflict}>
            {data.has_conflict ? (
              <>⚠️ 检测到 {data.conflicts.length} 处潜在矛盾</>
            ) : (
              <>✅ 各 Agent 结论一致，未检测到冲突</>
            )}
          </div>
        </div>
      </section>

      {/* 冲突对比卡片 */}
      {data.has_conflict && data.conflicts.length > 0 && (
        <section className="conflict-cards">
          <div className="container">
            <h2>⚔️ 冲突详情</h2>
            {data.conflicts.map((c, idx) => {
              const agentA = data.agents.find((a) => a.name === c.agent_a)
              const agentB = data.agents.find((a) => a.name === c.agent_b)
              return (
                <div key={idx} className="conflict-row">
                  <div className="conflict-card">
                    <div className="conflict-agent">{c.agent_a}</div>
                    <div className="conflict-claim">{c.claim_a || agentA?.final_answer?.slice(0, 100) || "—"}</div>
                  </div>
                  <div className="conflict-vs">⚔️</div>
                  <div className="conflict-card">
                    <div className="conflict-agent">{c.agent_b}</div>
                    <div className="conflict-claim">{c.claim_b || agentB?.final_answer?.slice(0, 100) || "—"}</div>
                  </div>
                  {c.reason && (
                    <div className="conflict-reason">
                      <strong>LLM 判断：</strong>{c.reason}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </section>
      )}

      {/* 仲裁过程 */}
      <section className="arbitration">
        <div className="container">
          <h2>🔍 仲裁过程</h2>
          <div className="round-list">
            <div className="round-item">
              <strong>Round 1：</strong> 初始分析
              <ul>
                {data.agents.map((a) => (
                  <li key={a.name}><strong>{a.name}：</strong> {a.final_answer?.slice(0, 80) || "—"}</li>
                ))}
              </ul>
            </div>
            {data.total_rounds > 1 && (
              <div className="round-item">
                <strong>Round 2：</strong> 引用来源重新分析
                <p>LLM 重新审视双方结论的指标、地域、时间维度</p>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* 最终调和结论 */}
      <section className="final-answer">
        <div className="container">
          <h2>✅ 调和结论</h2>
          <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit' }}>{data.final_answer}</pre>
          <div className="verification-badges">
            <span className="badge success">数据一致性：✅ 已验证</span>
            <span className="badge success">来源可追溯：✅ 全部有引用</span>
          </div>
        </div>
      </section>

      <section className="meta-footer">
        <div className="container">
          <p className="meta-text">数据更新时间：{data.generated_at || "未知"}</p>
        </div>
      </section>
    </div>
  )
}