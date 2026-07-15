import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import './Data.css'
import PageHeader from '../components/PageHeader'
import { fetchDataOverview, refreshData } from '../services/api'

// 数据页：抓取 / 整理 / 向量化状态总览，一个「刷新数据」按钮串起三动作

const KIND_LABELS = {
  official: '官方',
  news: '新闻',
  financial: '财报',
  social: '社区',
}

function ScrapeBadge({ status }) {
  if (status === 'ok') return <span className="data-badge ok">抓取正常</span>
  if (status === 'never') return <span className="data-badge never">从未抓取</span>
  return <span className="data-badge fail">抓取失败 · {status}</span>
}

export default function Data() {
  const [overview, setOverview] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [refreshing, setRefreshing] = useState(false)
  const [refreshError, setRefreshError] = useState(null)
  const navigate = useNavigate()

  useEffect(() => {
    let mounted = true
    fetchDataOverview()
      .then((data) => {
        if (!mounted) return
        setOverview(data)
        setLoading(false)
      })
      .catch((err) => {
        if (!mounted) return
        setLoadError(err.message)
        setLoading(false)
      })
    return () => {
      mounted = false
    }
  }, [])

  const handleRefresh = async () => {
    setRefreshing(true)
    setRefreshError(null)
    try {
      const { job_id } = await refreshData()
      navigate(`/progress/${job_id}`)
    } catch (err) {
      setRefreshError(err.status === 409 ? '已有刷新任务进行中，请稍候' : err.message)
      setRefreshing(false)
    }
  }

  if (loading) {
    return (
      <div className="data-page loading-screen">
        <div className="loading-pulse"></div>
        <p>正在加载数据状态...</p>
      </div>
    )
  }

  if (loadError) {
    return (
      <div className="data-page">
        <PageHeader title="数据" description="抓取 → 整理 → 向量化 状态总览" />
        <div className="container">
          <div className="error-card">
            <h3>⚠️ 数据状态加载失败</h3>
            <p>{loadError}</p>
          </div>
        </div>
      </div>
    )
  }

  const vs = overview?.vector_store ?? {}
  const attempt = overview?.last_scrape_attempt ?? {}
  const sources = overview?.sources ?? []

  return (
    <div className="data-page">
      <PageHeader title="数据" description="抓取 → 整理 → 向量化 状态总览" />
      <div className="container">
        {/* 工具条：右上「刷新数据」串起 抓取→整理→向量化 */}
        <div className="data-toolbar">
          <span className="data-toolbar-hint">一键重跑完整数据流水线（五阶段实时日志）</span>
          <button className="btn-primary" onClick={handleRefresh} disabled={refreshing}>
            {refreshing ? '正在创建任务…' : '刷新数据'}
          </button>
        </div>
        {refreshError && <div className="error-card">{refreshError}</div>}

        {/* 顶部概览卡 */}
        <section className="data-overview-grid">
          {[
            { label: '向量库 Collection', value: vs.active_collection || '—' },
            { label: '向量条目', value: vs.chunks_total ?? 0, unit: '条' },
            {
              label: '最近抓取',
              value: attempt.at || '—',
              sub: `成功 ${attempt.ok ?? 0} · 失败 ${attempt.failed ?? 0}`,
            },
            { label: '最近整理', value: overview?.summarized_at || '—' },
            { label: '整理模型', value: overview?.summarized_model || '—' },
          ].map((m, idx) => (
            <div key={idx} className="data-overview-card fade-in" style={{ animationDelay: `${idx * 60}ms` }}>
              <div className="data-overview-label">{m.label}</div>
              <div className="data-overview-value" title={m.value}>
                {m.value}
                {m.unit && <span className="data-overview-unit">{m.unit}</span>}
              </div>
              {m.sub && <div className="data-overview-sub">{m.sub}</div>}
            </div>
          ))}
        </section>

        {/* 数据源卡片 */}
        <section className="data-sources-section">
          <h2 className="section-title">📡 数据源（{sources.length}）</h2>
          <div className="data-sources-grid">
            {sources.map((src, idx) => (
              <div key={src.key} className="data-source-card fade-in" style={{ animationDelay: `${(idx + 5) * 60}ms` }}>
                <div className="data-source-header">
                  <span className="data-source-label">{src.label}</span>
                  <span className="data-badge kind">{KIND_LABELS[src.kind] || src.kind}</span>
                </div>
                <a className="data-source-url" href={src.url} target="_blank" rel="noreferrer" title={src.url}>
                  {src.url}
                </a>
                <div className="data-source-badges">
                  <ScrapeBadge status={src.scrape_status} />
                  {src.summarized ? (
                    <span className="data-badge ok">已整理</span>
                  ) : (
                    <span className="data-badge never">未整理</span>
                  )}
                </div>
                <div className="data-source-meta">
                  <span>抓取时间：{src.scraped_at || '—'}</span>
                  <span>正文 {src.text_length ?? 0} 字 · 关键事实 {src.key_facts_count ?? 0} 条</span>
                </div>
                {src.summary_preview && <p className="data-source-summary">{src.summary_preview}</p>}
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}
