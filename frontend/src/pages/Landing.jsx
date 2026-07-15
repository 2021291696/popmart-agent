import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import './Landing.css'
import { fetchScenarios } from '../services/api'

// 场景卡片的展示文案（图标/标题/描述），按看板页 key 映射；
// query、跳转目标与 cached 徽标以 /api/scenarios 返回为准
const SCENARIO_META = {
  executive: {
    icon: '📊',
    title: '老板早会页',
    desc: '每周一早会前，快速浏览市场趋势和核心 IP 表现，决定本周主推方向。',
    meta: ['目标用户：门店老板', '使用时机：周一早会前'],
  },
  supply: {
    icon: '📦',
    title: '备货分析页',
    desc: '深度分析 IP 销量趋势、库存周转率和区域偏好，精准决定进货量。',
    meta: ['目标用户：备货员', '使用时机：备货决策前'],
  },
  risk: {
    icon: '⚠️',
    title: '客诉应对页',
    desc: '实时监控消费者投诉、二手假货风险，快速准备应对话术和防伪指南。',
    meta: ['目标用户：分店员工', '使用时机：客户投诉后'],
  },
}

// 后端不可达时的回退场景（与后端预设一致，cached 置 false）
const FALLBACK_SCENARIOS = [
  { id: 'market', label: '综合市场表现', query: '泡泡玛特最近的市场表现如何？', page: 'executive', cached: false },
  { id: 'labubu', label: 'LABUBU IP 解析', query: 'LABUBU 为什么能成为泡泡玛特的核心IP？', page: 'supply', cached: false },
  { id: 'risk', label: '消费者风险', query: '泡泡玛特消费者投诉和二手假货风险有多高？', page: 'risk', cached: false },
]

export default function Landing() {
  const [scenarios, setScenarios] = useState(FALLBACK_SCENARIOS)

  useEffect(() => {
    fetchScenarios()
      .then((data) => {
        if (Array.isArray(data?.scenarios) && data.scenarios.length > 0) {
          setScenarios(data.scenarios)
        }
      })
      .catch(() => {
        // 后端不可达 → 保留回退场景卡片
      })
  }, [])

  return (
    <div className="landing">
      {/* Hero 区 - 视觉俘获 */}
      <section className="hero">
        <div className="container">
          <div className="hero-content">
            <div className="hero-text">
              <div className="eyebrow">生产级 Multi-Agent 系统</div>
              <h1>Multi-Agent 市场洞察<br/>辅助泡泡玛特分店决策</h1>
              <p className="hero-description">
                基于 ReAct 推理 + RAG 检索的智能分析系统，为门店老板、备货员、分店员工提供实时市场情报和消费者洞察。
                缓存命中秒级响应，首次分析约 30–140 秒。
              </p>
              <div className="hero-cta">
                <Link to="/chat" className="btn-primary">开始对话分析</Link>
                <a href="#scenarios" className="btn-secondary">查看示例看板</a>
              </div>

              {/* 可信度标签 */}
              <div className="trust-badges">
                <div className="badge">
                  <span className="badge-icon">⚡</span>
                  <span className="badge-text">预设场景已预热</span>
                </div>
                <div className="badge">
                  <span className="badge-icon">🔍</span>
                  <span className="badge-text">RAG 检索 &lt;2s</span>
                </div>
                <div className="badge">
                  <span className="badge-icon">🛡️</span>
                  <span className="badge-text">API 不可达自动降级</span>
                </div>
              </div>
            </div>

            <div className="hero-visual">
              <img src="/arch-system.svg" alt="Multi-Agent 系统架构" className="hero-img" />
            </div>
          </div>
        </div>
      </section>

      {/* 场景入口 - 快速操作区（数据来自 /api/scenarios，失败时回退内置卡片） */}
      <section id="scenarios" className="scenarios">
        <div className="container">
          <h2>三大应用场景</h2>
          <p className="section-subtitle">根据不同角色的决策需求，提供针对性的分析工具</p>

          <div className="scenario-grid">
            {scenarios.map((s) => {
              const meta = SCENARIO_META[s.page] || {
                icon: '📈',
                title: s.label,
                desc: s.query,
                meta: [],
              }
              return (
                <Link
                  key={s.id || s.page}
                  to={`/${s.page}`}
                  className="scenario-card"
                >
                  <div className="scenario-icon">{meta.icon}</div>
                  <h3>
                    {meta.title}
                    {s.cached && <span className="scenario-cached-badge">已预热 · 秒开</span>}
                  </h3>
                  <p>{meta.desc}</p>
                  <div className="scenario-meta">
                    {meta.meta.map((m) => (
                      <span key={m} className="meta-item">{m}</span>
                    ))}
                    <span className="meta-item">示例问题：{s.query}</span>
                  </div>
                  <span className="scenario-cta">查看示例 →</span>
                </Link>
              )
            })}
          </div>
        </div>
      </section>

      {/* 可信度支撑 - 证明生产级 */}
      <section id="features" className="features">
        <div className="container">
          <h2>为什么是生产级系统？</h2>
          <p className="section-subtitle">不只是 Demo，而是可维护、可扩展的企业级解决方案</p>

          <div className="feature-grid">
            {/* 特性 1：架构设计 */}
            <div className="feature-card">
              <div className="feature-header">
                <span className="feature-number">01</span>
                <h3>Multi-Agent 编排</h3>
              </div>
              <p>3 个专业 Agent（IP 情报 / 消费者洞察 / 防伪与二手）通过 Orchestrator 动态调度，支持并行推理和结果融合。</p>
              <div className="feature-visual">
                <img src="/arch-detail.svg" alt="可信度支撑" className="feature-img" />
              </div>
            </div>

            {/* 特性 2：错误处理 */}
            <div className="feature-card">
              <div className="feature-header">
                <span className="feature-number">02</span>
                <h3>健壮的错误处理</h3>
              </div>
              <p>实现了 ImprovementLoop 自愈机制，LLM 超时自动重试，数据缺失时降级到 Agent 直出结论，保证系统高可用。</p>
              <ul className="feature-list">
                <li>LLM 超时自动重试（最多 3 次）</li>
                <li>LLM 综合失败时降级策略</li>
                <li>Hook 观测系统实时监控</li>
              </ul>
            </div>

            {/* 特性 3：数据透明 */}
            <div className="feature-card">
              <div className="feature-header">
                <span className="feature-number">03</span>
                <h3>数据来源可追溯</h3>
              </div>
              <p>每条分析结论都标注来源 Agent 和调用的工具，展示完整 ReAct 推理过程，让决策有据可依。</p>
              <div className="feature-visual">
                <img src="/reasoning-flow.svg" alt="ReAct 推理过程" className="feature-img" />
              </div>
            </div>

            {/* 特性 4：性能优化 */}
            <div className="feature-card">
              <div className="feature-header">
                <span className="feature-number">04</span>
                <h3>性能与缓存</h3>
              </div>
              <p>
                跨 session 缓存持久化（.demo_cache.json），RAG 检索平均耗时 &lt;2s，预设场景已预热、演示秒级响应；
                API 不可达时自动切换本地演示数据。
              </p>
              <div className="performance-metrics">
                <div className="metric">
                  <span className="metric-value">秒级</span>
                  <span className="metric-label">缓存命中响应</span>
                </div>
                <div className="metric">
                  <span className="metric-value">&lt;2s</span>
                  <span className="metric-label">RAG 检索</span>
                </div>
                <div className="metric">
                  <span className="metric-value">3 层</span>
                  <span className="metric-label">错误重试</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 技术架构 */}
      <section id="architecture" className="architecture">
        <div className="container">
          <h2>系统架构</h2>
          <p className="section-subtitle">基于 ReAct 推理范式 + RAG 检索增强的 Multi-Agent 编排系统</p>

          <div className="architecture-diagram">
            <img src="/arch-detail.svg" alt="完整系统架构" className="feature-img" />
          </div>

          <div className="tech-stack">
            <h3>技术栈</h3>
            <div className="stack-grid">
              <div className="stack-item">
                <strong>后端框架</strong>
                <span>Python + FastAPI（Streamlit 调试台）</span>
              </div>
              <div className="stack-item">
                <strong>LLM</strong>
                <span>DeepSeek（OpenAI 兼容）/ 可切换</span>
              </div>
              <div className="stack-item">
                <strong>向量数据库</strong>
                <span>ChromaDB</span>
              </div>
              <div className="stack-item">
                <strong>嵌入模型</strong>
                <span>Sentence Transformers</span>
              </div>
              <div className="stack-item">
                <strong>爬虫</strong>
                <span>Scrapling + BeautifulSoup</span>
              </div>
              <div className="stack-item">
                <strong>测试</strong>
                <span>pytest + pytest-asyncio</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA 区 */}
      <section className="cta">
        <div className="container">
          <div className="cta-content">
            <h2>开始使用</h2>
            <p>选择一个场景，体验 AI Agent 如何辅助业务决策</p>
            <div className="cta-buttons">
              <Link to="/executive" className="btn-primary">老板早会页</Link>
              <Link to="/supply" className="btn-primary">备货分析页</Link>
              <Link to="/risk" className="btn-primary">客诉应对页</Link>
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}
