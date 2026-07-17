import React, { useState } from 'react'
import './Supply.css'
import PageHeader from '../components/PageHeader'
import MarkdownView from '../components/MarkdownView'
import { BoardEmptyState, BoardToolbar } from '../components/BoardChrome'
import { IpMentionsChart, SentimentDonut, SentimentIntensityChart } from '../components/BoardCharts'
import { useBoard } from '../hooks/useBoard'

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
  const { data, status, error, refresh } = useBoard('supply')
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
      <div className="supply-page loading-screen">
        <div className="loading-pulse"></div>
        <p>正在加载备货分析看板...</p>
      </div>
    )
  }

  if (status === 'empty') {
    return (
      <div className="supply-page">
        <PageHeader title="备货分析" description="Agent ReAct 推理过程" />
        <div className="container">
          <BoardEmptyState onRefresh={handleRefresh} refreshing={refreshing} refreshError={refreshError} />
        </div>
      </div>
    )
  }

  if (status === 'error') {
    return (
      <div className="supply-page">
        <PageHeader title="备货分析" description="Agent ReAct 推理过程" />
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

  const agent = data?.agent
  const tools = data.tool_distribution || []
  const maxCalls = Math.max(...tools.map((t) => t.calls), 1)

  return (
    <div className="supply-page">
      <PageHeader
        title={data.title}
        description={agent ? `${agent.name} · ${agent.total_steps ?? 0} 步 ReAct 推理 · ${agent.llm_calls ?? 0} 次 LLM 调用` : 'ReAct 推理过程'}
      />

      <div className="container">
        <BoardToolbar query={data.query} onRefresh={handleRefresh} refreshing={refreshing} refreshError={refreshError} />

        {/* Agent 元信息 */}
        {agent && (
          <section className="agent-meta-row">
            {[
              { label: 'Agent', value: agent.name },
              { label: '推理步数', value: agent.total_steps ?? 0 },
              { label: 'LLM 调用', value: agent.llm_calls ?? 0 },
              { label: '数据调用', value: tools.reduce((a, b) => a + b.calls, 0) },
            ].map((m, idx) => (
              <div key={idx} className="agent-meta-card fade-in" style={{ animationDelay: `${idx * 80}ms` }}>
                <div className="agent-meta-label">{m.label}</div>
                <div className="agent-meta-value">{m.value}</div>
              </div>
            ))}
          </section>
        )}

        {/* 热度与情感图表（后端预提取的 charts，缺失的图自动跳过） */}
        {data.charts && (data.charts.ip_mentions || data.charts.sentiment) && (
          <section className="charts-section">
            <h2 className="section-title">📊 热度与情感速览</h2>
            <div className="charts-grid">
              <IpMentionsChart data={data.charts.ip_mentions} />
              <SentimentDonut sentiment={data.charts.sentiment} />
              <SentimentIntensityChart sentiment={data.charts.sentiment} />
            </div>
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
              {tools.map((t) => (
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
