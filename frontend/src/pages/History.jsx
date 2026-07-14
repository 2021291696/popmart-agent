import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import './History.css'
import PageHeader from '../components/PageHeader'
import { fetchHistory } from '../services/api'

const PAGE_LABELS = {
  executive: '老板早会',
  supply: '备货分析',
  risk: '客诉应对',
}

export default function History() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchHistory()
      .then((data) => {
        setItems(data.items || [])
        setLoading(false)
      })
      .catch((err) => {
        setError(err.message)
        setLoading(false)
      })
  }, [])

  if (loading) {
    return (
      <div className="history-page loading-screen">
        <div className="loading-pulse"></div>
        <p>正在加载历史数据...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="history-page">
        <PageHeader title="历史数据" description="所有分析过的记录" />
        <div className="container">
          <div className="error-card">{error}</div>
        </div>
      </div>
    )
  }

  return (
    <div className="history-page">
      <PageHeader title="历史数据" description={`共 ${items.length} 条分析记录，可点击回看`} />
      <div className="container">
        {items.length === 0 ? (
          <div className="empty-state">
            <p>暂无分析记录</p>
            <Link to="/chat" className="btn-primary">去对话分析</Link>
          </div>
        ) : (
          <div className="history-list">
            {items.map((item, idx) => {
              const page = item.recommended_page || 'executive'
              return (
                <div key={idx} className="history-card fade-in" style={{ animationDelay: `${idx * 60}ms` }}>
                  <div className="history-main">
                    <div className="history-query">{item.query}</div>
                    <div className="history-meta">
                      <span>{item.saved_at || '未知时间'}</span>
                      <span>{item.total_agents || 0} 个 Agent</span>
                      <span>{item.elapsed_seconds || 0}s</span>
                    </div>
                    {item.snippet && <p className="history-snippet">{item.snippet}...</p>}
                  </div>
                  <div className="history-actions">
                    <Link to={`/${page}?query=${encodeURIComponent(item.query)}`} className="btn-secondary">
                      查看{PAGE_LABELS[page] || '报告'}
                    </Link>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
