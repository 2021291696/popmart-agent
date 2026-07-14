import { useEffect, useRef, useState } from 'react'
import { getJob, subscribeJobEvents } from '../services/api'

// REST 完成态是 'completed'，SSE 结束帧 stage 是 'complete'，两处统一按完成处理
const COMPLETE_STATUSES = ['complete', 'completed']
const TERMINAL_STATUSES = [...COMPLETE_STATUSES, 'failed']

export function isCompleteStatus(status) {
  return COMPLETE_STATUSES.includes(status)
}

export function isTerminalStatus(status) {
  return TERMINAL_STATUSES.includes(status)
}

function classifyError(err) {
  const msg = err?.message || ''
  if (/HTTP (401|403)/.test(msg)) return 'auth'
  if (/HTTP 404/.test(msg)) return 'not_found'
  return 'generic'
}

const ERROR_TEXT = {
  auth: '需要 API Key：服务端已开启认证，请配置 VITE_API_KEY 后刷新重试',
  not_found: '任务不存在或已过期（后端可能已重启），请重新发起分析',
}

const POLL_INTERVAL_MS = 2000
const COMPLETE_RETRY_MS = 800

export function useJob(jobId) {
  const [status, setStatus] = useState('pending')
  const [events, setEvents] = useState([])
  // error: { kind: 'auth' | 'not_found' | 'generic', message } | null
  const [error, setError] = useState(null)
  const [job, setJob] = useState(null)
  const esRef = useRef(null)
  const pollRef = useRef(null)
  const retryRef = useRef(null)

  useEffect(() => {
    if (!jobId) return

    let mounted = true
    // SSE 断线自动重连时后端会重放历史帧，按 时间戳+stage+消息 去重
    // （agent_complete 等 stage 会多次出现，必须带上 message 区分合法帧）
    const seenEvents = new Set()

    const stopStreams = () => {
      if (esRef.current) {
        esRef.current.close()
        esRef.current = null
      }
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
    }

    const fail = (kind, message) => {
      if (!mounted) return
      setError({ kind, message: message || ERROR_TEXT[kind] || '未知错误' })
    }

    const applyJob = (data) => {
      if (!mounted) return
      setJob(data)
      setStatus(data.status)
      // complete 竞态兜底：完成态但 recommended_page 仍为空时，
      // 延迟重查一次再让页面跳转（后端写缓存与发帧之间的窗口期）
      if (isCompleteStatus(data.status) && !data.recommended_page && !retryRef.current) {
        retryRef.current = setTimeout(() => {
          retryRef.current = null
          getJob(jobId)
            .then((fresh) => {
              if (mounted) applyJob(fresh)
            })
            .catch(() => {})
        }, COMPLETE_RETRY_MS)
      }
    }

    // SSE 失败 → 降级为 REST 轮询（每 2s，直到 terminal）
    const startPolling = () => {
      if (pollRef.current || !mounted) return
      pollRef.current = setInterval(async () => {
        try {
          const data = await getJob(jobId)
          if (!mounted) return
          applyJob(data)
          if (isTerminalStatus(data.status)) {
            clearInterval(pollRef.current)
            pollRef.current = null
          }
        } catch (err) {
          if (!mounted) return
          const kind = classifyError(err)
          // 认证/任务丢失是终态错误，停止轮询并提示；其余视为网络抖动继续轮询
          if (kind === 'auth' || kind === 'not_found') {
            clearInterval(pollRef.current)
            pollRef.current = null
            fail(kind)
          }
        }
      }, POLL_INTERVAL_MS)
    }

    getJob(jobId)
      .then((data) => {
        if (!mounted) return
        applyJob(data)
        // 初始即为终态（页面刷新/直接打开链接）→ 不依赖 SSE 重放，直接完成
        if (isTerminalStatus(data.status)) return

        esRef.current = subscribeJobEvents(
          jobId,
          (event) => {
            if (!mounted) return
            const key = `${event.timestamp || ''}|${event.stage}|${event.message || ''}`
            if (seenEvents.has(key)) return
            seenEvents.add(key)
            setEvents((prev) => [...prev, event])
            if (event.stage === 'complete') {
              setStatus('complete')
              // 后端保证 complete 帧带 recommended_page，但仍以 REST 为准刷新兜底
              getJob(jobId).then(applyJob).catch(() => {})
            } else if (event.stage === 'failed') {
              setStatus('failed')
              getJob(jobId).then(applyJob).catch(() => {})
            }
          },
          () => {
            // SSE 连接失败/断开（含认证开启时 EventSource 无法带 x-api-key 的 401）
            if (!mounted) return
            if (esRef.current) {
              esRef.current.close()
              esRef.current = null
            }
            startPolling()
          },
        )
      })
      .catch((err) => {
        if (!mounted) return
        fail(classifyError(err), err.message && classifyError(err) === 'generic' ? err.message : undefined)
      })

    return () => {
      mounted = false
      stopStreams()
      if (retryRef.current) {
        clearTimeout(retryRef.current)
        retryRef.current = null
      }
    }
  }, [jobId])

  return { status, events, error, job }
}
