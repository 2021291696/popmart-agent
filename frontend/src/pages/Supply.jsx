import React, { useEffect, useState } from 'react'
import './Supply.css'
import PageHeader from '../components/PageHeader'
import { fetchSupplyViz } from '../services/api'

export default function Supply() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchSupplyViz()
      .then((viz) => {
        setData(viz)
        setLoading(false)
      })
      .catch((err) => {
        setError(err.message)
        setLoading(false)
      })
  }, [])

  if (loading) return <div className="supply-page"><PageHeader title="加载中..." /></div>
  if (error) return (
    <div className="supply-page">
      <PageHeader title="备货分析页" description="Agent ReAct 推理时间线" />
      <div className="error-banner">
        <h3>⚠️ 数据未就绪</h3>
        <p>{error}</p>
        <p>请先在 Streamlit 主入口跑一次分析预热缓存。</p>
      </div>
    </div>
  )

  const agent = data?.agent

  return (
    <div className="supply-page" data-source="visualize-api">
      <PageHeader
        title={data.title || "LABUBU IP 深度分析"}
        description={agent ? `${agent.name} · ReAct 推理过程` : "ReAct 推理过程"}
      />

      {/* Agent 基本信息 */}
      {agent && (
        <section className="agent-info">
          <div className="container">
            <div className="info-grid">
              <div className="info-item">
                <span className="info-label">Agent</span>
                <span className="info-value">{agent.name}</span>
              </div>
              <div className="info-item">
                <span className="info-label">推理步数</span>
                <span className="info-value">{agent.total_steps}</span>
              </div>
              <div className="info-item">
                <span className="info-label">LLM 调用</span>
                <span className="info-value">{agent.llm_calls}</span>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* ReAct 循环时间线 */}
      <section className="react-timeline">
        <div className="container">
          <h2>🔄 ReAct 循环时间线</h2>
          {agent?.steps?.length > 0 ? (
            <div className="timeline">
              {agent.steps.map((step, idx) => (
                <div key={idx} className="timeline-item">
                  <div className="timeline-marker">Step {step.step}</div>
                  <div className="timeline-content">
                    {step.thought && (
                      <div className="step-thought">
                        <span className="step-label">💭 Thought:</span>
                        <p>{step.thought}</p>
                      </div>
                    )}
                    <div className="step-action">
                      <span className="step-label">⚡ Action:</span>
                      <code>{step.action}</code>
                      {step.action_input && (
                        <pre className="action-input">{step.action_input}</pre>
                      )}
                    </div>
                    {step.result && (
                      <div className="step-observation">
                        <span className="step-label">👁 Observation:</span>
                        <pre>{step.result}</pre>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="empty-state">该 Agent 未执行 ReAct 步骤</p>
          )}
        </div>
      </section>

      {/* 工具调用统计 */}
      {data.tool_distribution?.length > 0 && (
        <section className="tool-stats">
          <div className="container">
            <h2>🛠 工具调用统计</h2>
            <table className="stats-table">
              <thead>
                <tr>
                  <th>工具</th>
                  <th>调用次数</th>
                </tr>
              </thead>
              <tbody>
                {data.tool_distribution.map((t) => (
                  <tr key={t.name}>
                    <td><code>{t.name}</code></td>
                    <td>{t.calls}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* 最终结论 */}
      <section className="final-answer">
        <div className="container">
          <h2>✅ 最终结论</h2>
          <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit' }}>{data.final_answer}</pre>
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