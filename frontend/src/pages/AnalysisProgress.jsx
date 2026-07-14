import React, { useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import './AnalysisProgress.css'
import PageHeader from '../components/PageHeader'
import { useJob } from '../hooks/useJob'

const STAGES = [
  { key: 'decompose', label: '任务分解' },
  { key: 'agent_complete', label: 'Agent 执行' },
  { key: 'conflict_detect', label: '冲突检测' },
  { key: 'synthesize', label: '综合报告' },
  { key: 'complete', label: '完成' },
]

export default function AnalysisProgress() {
  const { jobId } = useParams()
  const navigate = useNavigate()
  const { status, events, error, job } = useJob(jobId)

  useEffect(() => {
    if (status === 'complete' && job?.recommended_page && job?.query) {
      const page = job.recommended_page
      navigate(`/${page}?query=${encodeURIComponent(job.query)}`)
    }
  }, [status, job, navigate])

  const reachedStages = new Set(events.map((e) => e.stage))
  const currentIndex = STAGES.findIndex((s) => !reachedStages.has(s.key))
  const activeIndex = currentIndex === -1 ? STAGES.length - 1 : currentIndex

  return (
    <div className="progress-page">
      <PageHeader title="分析中" description="Multi-Agent 正在协作分析，请稍候" />
      <div className="container">
        <div className="stage-bar">
          {STAGES.map((stage, idx) => (
            <div
              key={stage.key}
              className={`stage-item ${idx <= activeIndex ? 'active' : ''} ${reachedStages.has(stage.key) ? 'done' : ''}`}
            >
              <div className="stage-dot">{idx + 1}</div>
              <div className="stage-label">{stage.label}</div>
            </div>
          ))}
        </div>

        <div className="event-log">
          {events.map((ev, idx) => (
            <div key={idx} className="event-row">
              <span className="event-stage">{ev.stage}</span>
              <span className="event-message">{ev.message}</span>
            </div>
          ))}
          {status !== 'complete' && status !== 'failed' && (
            <div className="event-row pulse">
              <span className="event-stage">{status}</span>
              <span className="event-message">正在处理...</span>
            </div>
          )}
        </div>

        {error && <div className="error-card">分析失败：{error}</div>}
      </div>
    </div>
  )
}
