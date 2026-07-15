import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import './Chat.css'
import PageHeader from '../components/PageHeader'
import { startJob } from '../services/api'

export default function Chat() {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!query.trim()) return
    setLoading(true)
    setError(null)
    try {
      const { job_id } = await startJob(query)
      navigate(`/progress/${job_id}`)
    } catch (err) {
      setError(err.message)
      setLoading(false)
    }
  }

  return (
    <div className="chat-page">
      <PageHeader title="对话分析" description="输入任何关于泡泡玛特的问题，Multi-Agent 将自动分析并生成报告" />
      <div className="container">
        <form className="chat-form" onSubmit={handleSubmit}>
          <textarea
            className="chat-input"
            rows={4}
            placeholder="例如：泡泡玛特最近的市场表现如何？LABUBU 为什么能成为核心 IP？消费者投诉风险有多高？"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? '正在创建任务...' : '开始分析'}
          </button>
        </form>
        {error && <div className="error-card">{error}</div>}
      </div>
    </div>
  )
}
