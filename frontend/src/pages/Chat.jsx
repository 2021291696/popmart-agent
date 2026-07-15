import React, { useCallback, useEffect, useRef, useState } from 'react'
import { Menu, Plus, Send } from 'lucide-react'
import './Chat.css'
import MarkdownView from '../components/MarkdownView'
import { fetchChatSession, fetchChatSessions, postChat } from '../services/api'

// 对话分析页：纯 RAG 问答客户端（DeepSeek/ChatGPT 式布局）
// 左侧会话列表 + 右侧气泡对话，与三看板完全独立，不触发多 Agent 编排

const QUERY_TYPE_LABELS = { fact: '事实型', analysis: '分析型' }

export default function Chat() {
  const [sessions, setSessions] = useState([])
  const [activeSessionId, setActiveSessionId] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [sendError, setSendError] = useState(null)
  const [loadingMessages, setLoadingMessages] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  // 聊天页为应用式固定布局：锁定 body 滚动，仅消息区内部滚动
  useEffect(() => {
    document.body.classList.add('chat-lock')
    return () => document.body.classList.remove('chat-lock')
  }, [])

  const refreshSessions = useCallback(() => {
    fetchChatSessions()
      .then((data) => setSessions(data.items || []))
      .catch((err) => console.warn('[chat] 会话列表加载失败:', err.message))
  }, [])

  useEffect(() => {
    refreshSessions()
  }, [refreshSessions])

  // 新消息到达时滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, sending])

  const openSession = (id) => {
    if (sending || id === activeSessionId) return
    setSidebarOpen(false)
    setSendError(null)
    setLoadingMessages(true)
    setActiveSessionId(id)
    fetchChatSession(id)
      .then((session) => setMessages(session.messages || []))
      .catch((err) => {
        console.warn('[chat] 会话加载失败:', err.message)
        setMessages([])
        setActiveSessionId(null)
        setSendError('会话加载失败，可能已被清理，请新建会话')
      })
      .finally(() => setLoadingMessages(false))
  }

  const startNewSession = () => {
    if (sending) return
    setSidebarOpen(false)
    setActiveSessionId(null)
    setMessages([])
    setSendError(null)
    inputRef.current?.focus()
  }

  const send = async () => {
    const text = input.trim()
    if (!text || sending) return
    setSendError(null)
    setInput('')
    // 乐观上屏用户消息；失败时后端不会落库，仅展示错误提示
    setMessages((prev) => [...prev, { role: 'user', content: text }])
    setSending(true)
    try {
      const resp = await postChat(text, activeSessionId)
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: resp.answer,
          sources: resp.sources || [],
          confidence_label: resp.confidence_label,
          query_type: resp.query_type,
        },
      ])
      if (!activeSessionId) setActiveSessionId(resp.session_id)
      // 新会话首条消息后刷新侧栏（标题由后端取首条用户消息生成）
      refreshSessions()
    } catch (err) {
      // 502 = LLM 失败（detail 含原因）；其余按网络/服务异常提示
      const detail = err.status === 502 ? 'LLM 调用失败，请稍后重试' : '发送失败，请检查服务后重试'
      setSendError(`${detail}（${err.message}）`)
    } finally {
      setSending(false)
      inputRef.current?.focus()
    }
  }

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      send()
    }
  }

  return (
    <div className="chat-page">
      {/* 左侧会话列表 */}
      <aside className={`chat-sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div className="chat-sidebar-header">
          <button className="chat-new-btn" onClick={startNewSession} disabled={sending}>
            <Plus size={16} />
            <span>新会话</span>
          </button>
        </div>
        <div className="chat-session-list">
          {sessions.length === 0 ? (
            <p className="chat-session-empty">暂无历史会话</p>
          ) : (
            sessions.map((s) => (
              <button
                key={s.id}
                className={`chat-session-item ${s.id === activeSessionId ? 'active' : ''}`}
                onClick={() => openSession(s.id)}
                title={s.title}
              >
                <span className="chat-session-title">{s.title || '新会话'}</span>
                <span className="chat-session-count">{s.message_count} 条消息</span>
              </button>
            ))
          )}
        </div>
      </aside>
      {sidebarOpen && <div className="chat-sidebar-mask" onClick={() => setSidebarOpen(false)} />}

      {/* 右侧对话区 */}
      <section className="chat-main">
        <div className="chat-main-header">
          <button className="chat-sidebar-toggle" onClick={() => setSidebarOpen(true)} aria-label="会话列表">
            <Menu size={18} />
          </button>
          <span className="chat-main-title">对话分析 · RAG 问答</span>
        </div>

        <div className="chat-messages">
          {messages.length === 0 && !loadingMessages ? (
            <div className="chat-welcome">
              <h2>向知识库提问</h2>
              <p>基于已抓取与向量化的泡泡玛特资料作答，附来源与置信度</p>
              <div className="chat-welcome-examples">
                {['泡泡玛特的核心 IP 有哪些？', 'LABUBU 为什么受欢迎？', '消费者投诉集中在哪些方面？'].map((q) => (
                  <button key={q} className="chat-example-chip" onClick={() => setInput(q)}>
                    {q}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((m, idx) => (
              <div key={idx} className={`chat-row ${m.role}`}>
                <div className={`chat-bubble ${m.role}`}>
                  {m.role === 'assistant' ? (
                    <MarkdownView content={m.content} />
                  ) : (
                    <span className="chat-user-text">{m.content}</span>
                  )}
                  {m.role === 'assistant' && (m.sources?.length > 0 || m.confidence_label) && (
                    <div className="chat-meta">
                      {m.confidence_label && (
                        <span className="chat-chip confidence">置信度：{m.confidence_label}</span>
                      )}
                      {m.query_type && (
                        <span className="chat-chip query-type">{QUERY_TYPE_LABELS[m.query_type] || m.query_type}</span>
                      )}
                      {(m.sources || []).map((src) => (
                        <span key={src} className="chat-chip source" title={src}>
                          {src}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
          {loadingMessages && <p className="chat-loading-hint">正在加载会话...</p>}
          {sending && (
            <div className="chat-row assistant">
              <div className="chat-bubble assistant thinking">
                <span className="chat-thinking-dot"></span>
                正在检索与分析…
              </div>
            </div>
          )}
          {sendError && (
            <div className="chat-row assistant">
              <div className="chat-bubble assistant chat-error">{sendError}</div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="chat-input-area">
          <textarea
            ref={inputRef}
            className="chat-input"
            rows={2}
            placeholder="输入问题，Enter 发送，Shift+Enter 换行"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            disabled={sending}
          />
          <button className="chat-send-btn" onClick={send} disabled={sending || !input.trim()} aria-label="发送">
            <Send size={18} />
          </button>
        </div>
      </section>
    </div>
  )
}
