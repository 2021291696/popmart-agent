import React from 'react'
import { Link } from 'react-router-dom'
import './Landing.css'

export default function Landing() {
  return (
    <div className="landing">
      {/* Nav/Footer/Banner 已移至 App.jsx 统一管理 */}

      {/* Hero 区 - 视觉俘获 */}
      <section className="hero">
        <div className="container">
          <div className="hero-content">
            <div className="hero-text">
              <div className="eyebrow">生产级 Multi-Agent 系统</div>
              <h1>3 秒获取市场洞察<br/>辅助泡泡玛特分店决策</h1>
              <p className="hero-description">
                基于 ReAct 推理 + RAG 检索的智能分析系统，为门店老板、备货员、分店员工提供实时市场情报和消费者洞察。
              </p>
              <div className="hero-cta">
                <Link to="/chat" className="btn-primary">开始对话分析</Link>
                <a href="#scenarios" className="btn-secondary">查看示例看板</a>
              </div>

              {/* 可信度标签 */}
              <div className="trust-badges">
                <div className="badge">
                  <span className="badge-icon">⚡</span>
                  <span className="badge-text">缓存命中率 85%</span>
                </div>
                <div className="badge">
                  <span className="badge-icon">🔍</span>
                  <span className="badge-text">RAG 检索 &lt;2s</span>
                </div>
                <div className="badge">
                  <span className="badge-icon">🛡️</span>
                  <span className="badge-text">自动降级策略</span>
                </div>
              </div>
            </div>

            <div className="hero-visual">
              <img src="/arch-system.svg" alt="Multi-Agent 系统架构" className="hero-img" />
            </div>
          </div>
        </div>
      </section>

      {/* 场景入口 - 快速操作区 */}
      <section id="scenarios" className="scenarios">
        <div className="container">
          <h2>三大应用场景</h2>
          <p className="section-subtitle">根据不同角色的决策需求，提供针对性的分析工具</p>

          <div className="scenario-grid">
            {/* 场景 1：老板早会 */}
            <Link to="/executive" className="scenario-card">
              <div className="scenario-icon">📊</div>
              <h3>老板早会页</h3>
              <p>每周一早会前，快速浏览市场趋势和核心 IP 表现，决定本周主推方向。</p>
              <div className="scenario-meta">
                <span className="meta-item">目标用户：门店老板</span>
                <span className="meta-item">使用时机：周一早会前</span>
              </div>
              <span className="scenario-cta">查看示例 →</span>
            </Link>

            {/* 场景 2：备货分析 */}
            <Link to="/supply" className="scenario-card">
              <div className="scenario-icon">📦</div>
              <h3>备货分析页</h3>
              <p>深度分析 IP 销量趋势、库存周转率和区域偏好，精准决定进货量。</p>
              <div className="scenario-meta">
                <span className="meta-item">目标用户：备货员</span>
                <span className="meta-item">使用时机：备货决策前</span>
              </div>
              <span className="scenario-cta">查看示例 →</span>
            </Link>

            {/* 场景 3：客诉应对 */}
            <Link to="/risk" className="scenario-card">
              <div className="scenario-icon">⚠️</div>
              <h3>客诉应对页</h3>
              <p>实时监控消费者投诉、二手假货风险，快速准备应对话术和防伪指南。</p>
              <div className="scenario-meta">
                <span className="meta-item">目标用户：分店员工</span>
                <span className="meta-item">使用时机：客户投诉后</span>
              </div>
              <span className="scenario-cta">查看示例 →</span>
            </Link>
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
                <li>API 超时自动重试（最多 3 次）</li>
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
              <p>跨 session 缓存持久化（.demo_cache.json），RAG 检索平均耗时 &lt;2s，缓存命中率 85%，面试演示秒级响应。</p>
              <div className="performance-metrics">
                <div className="metric">
                  <span className="metric-value">85%</span>
                  <span className="metric-label">缓存命中率</span>
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
                <span>Python + Streamlit</span>
              </div>
              <div className="stack-item">
                <strong>LLM</strong>
                <span>OpenAI / Anthropic</span>
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
      {/* Nav/Footer/Banner 已移至 App.jsx 统一管理 */}
        </div>
      </section>
    </div>
  )
}
