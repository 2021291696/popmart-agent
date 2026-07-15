import React, { useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import './AnalysisProgress.css'
import PageHeader from '../components/PageHeader'
import { useJob, isCompleteStatus, isTerminalStatus } from '../hooks/useJob'

// conflict_resolve 归入「冲突检测」一格；complete/completed 双轨统一
const STAGES = [
  { key: 'decompose', label: '任务分解', match: ['decompose'] },
  { key: 'agent_complete', label: 'Agent 执行', match: ['agent_complete'] },
  { key: 'conflict', label: '冲突检测', match: ['conflict_detect', 'conflict_resolve'] },
  { key: 'synthesize', label: '综合报告', match: ['synthesize'] },
  { key: 'complete', label: '完成', match: ['complete', 'completed'] },
]

export default function AnalysisProgress() {
  const { jobId } = useParams()
  const navigate = useNavigate()
  const { status, events, error, job } = useJob(jobId)

  const completed = isCompleteStatus(status)
  const failed = status === 'failed'

  // 完成后按 recommended_page 跳回对应页面：
  // "data" → 数据页；executive/supply/risk → 对应看板（读自己的缓存，不带 query 参数）
  useEffect(() => {
    if (completed && job?.recommended_page) {
      navigate(`/${job.recommended_page}`)
    }
  }, [completed, job, navigate])

  const reachedStages = new Set(events.map((e) => e.stage))
  const isReached = (stage) => stage.match.some((k) => reachedStages.has(k))
  const currentIndex = STAGES.findIndex((s) => !isReached(s))
  const activeIndex = currentIndex === -1 ? STAGES.length - 1 : currentIndex

  // 失败信息来源优先级：REST job.error → SSE failed 帧 payload → failed 帧 message
  const failedEvent = events.find((e) => e.stage === 'failed')
  const failMessage =
    job?.error || failedEvent?.payload?.error || failedEvent?.message || '分析过程中出现错误，请重试'

  return (
    <div className="progress-page">
      <PageHeader title="分析中" description="Multi-Agent 正在协作分析，请稍候" />
      <div className="container">
        <div className="stage-bar">
          {STAGES.map((stage, idx) => (
            <div
              key={stage.key}
              className={`stage-item ${idx <= activeIndex ? 'active' : ''} ${isReached(stage) ? 'done' : ''} ${
                failed && idx === activeIndex ? 'failed' : ''
              }`}
            >
              <div className="stage-dot">{failed && idx === activeIndex ? '✕' : idx + 1}</div>
              <div className="stage-label">{stage.label}</div>
            </div>
          ))}
        </div>

        <div className="event-log">
          {events.map((ev, idx) => (
            <div key={idx} className={`event-row ${ev.stage === 'failed' ? 'event-row-failed' : ''}`}>
              <span className="event-stage">{ev.stage}</span>
              <span className="event-message">{ev.message}</span>
            </div>
          ))}
          {!isTerminalStatus(status) && !error && (
            <div className="event-row pulse">
              <span className="event-stage">{status}</span>
              <span className="event-message">正在处理...</span>
            </div>
          )}
        </div>

        {failed && (
          <div className="error-card">
            <h3>⚠️ 分析失败</h3>
            <p>{failMessage}</p>
            <p className="error-hint">
              <Link to="/">返回首页</Link>
            </p>
          </div>
        )}

        {error && (
          <div className="error-card">
            <h3>{error.kind === 'not_found' ? '⚠️ 任务不存在或已过期' : '⚠️ 连接异常'}</h3>
            <p>{error.message}</p>
            <p className="error-hint">
              <Link to="/">返回首页</Link>
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
