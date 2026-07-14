import React, { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import './Supply.css'
import PageHeader from '../components/PageHeader'
import MarkdownView from '../components/MarkdownView'
import { fetchSupplyViz } from '../services/api'

function ToolBar({ name, count, max }) {
  const pct = max > 0 ? (count / max) * 100 : 0
  return (
    <div className="tool-bar">
      <div className="tool-bar-label">
        <code>{name}</code>
        <span>{count}</span>
      </div>
      <div className="tool-bar-track">
        <div className="tool-bar-fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export default function Supply() {
  const [searchParams] = useSearchParams()
  const query = searchParams.get('query') || ''
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    fetchSupplyViz(query)
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
      <div className="supply-page loading-screen">
        <div className="loading-pulse"></div>
        <p>正在加载 IP 深度分析...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="supply-page">
        <PageHeader title="LABUBU IP 深度分析" description="Agent ReAct 推理过程" />
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

  const agent = data?.agent
  const tools = data.tool_distribution || []
  const maxCalls = Math.max(...tools.map((t) => t.calls), 1)

  return (
    <div className="supply-page">
      <PageHeader
        title={data.title}
        description={agent ? `${agent.name} · ${agent.total_steps} 步 ReAct 推理 · ${agent.llm_calls} 次 LLM 调用` : 'ReAct 推理过程'}
      />

      <div className="container">
        {/* Agent 元信息 */}
        {agent && (
          <section className="agent-meta-row">
            {[
              { label: 'Agent', value: agent.name },
              { label: '推理步数', value: agent.total_steps },
              { label: 'LLM 调用', value: agent.llm_calls },
              { label: '数据调用', value: tools.reduce((a, b) => a + b.calls, 0) },
            ].map((m, idx) => (
              <div key={idx} className="agent-meta-card fade-in" style={{ animationDelay: `${idx * 80}ms` }}>
                <div className="agent-meta-label">{m.label}</div>
                <div className="agent-meta-value">{m.value}</div>
              </div>
            ))}
          </section>
        )}

        {/* ReAct 时间线 */}
        <section className="timeline-section">
          <h2 className="section-title">🔄 ReAct 循环时间线</h2>
          {agent?.steps?.length > 0 ? (
            <div className="timeline">
              {agent.steps.map((step, idx) => (
                <div key={idx} className="timeline-item fade-in" style={{ animationDelay: `${(idx + 4) * 80}ms` }}>
                  <div className="timeline-left">
                    <div className="timeline-dot">{step.step}</div>
                    {idx !== agent.steps.length - 1 && <div className="timeline-line" />}
                  </div>
                  <div className="timeline-content">
                    {step.thought && (
                      <div className="timeline-block thought">
                        <div className="block-label">💭 Thought</div>
                        <p>{step.thought}</p>
                      </div>
                    )}
                    <div className="timeline-block action">
                      <div className="block-label">⚡ Action</div>
                      <code className="action-name">{step.action}</code>
                      {step.action_input && step.action_input !== 'null' && (
                        <pre className="action-input">{step.action_input}</pre>
                      )}
                    </div>
                    {step.result && (
                      <div className="timeline-block observation">
                        <div className="block-label">👁 Observation</div>
                        <pre className="observation-result">{step.result}</pre>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="empty-state">该 Agent 未执行 ReAct 步骤</p>
          )}
        </section>

        {/* 工具调用统计 */}
        {tools.length > 0 && (
          <section className="tools-section">
            <h2 className="section-title">🛠 工具调用统计</h2>
            <div className="tools-card">
              {tools.map((t, idx) => (
                <ToolBar key={t.name} name={t.name} count={t.calls} max={maxCalls} />
              ))}
            </div>
          </section>
        )}

        {/* 最终结论 */}
        <section className="report-section">
          <h2 className="section-title">✅ 最终结论</h2>
          <div className="report-card">
            <MarkdownView content={data.final_answer} />
          </div>
        </section>

        <footer className="page-footer">
          数据更新时间：{data.generated_at || '未知'}
        </footer>
      </div>
    </div>
  )
}