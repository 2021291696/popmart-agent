// API 客户端 - 三层降级策略：后端 API → 本地副本 → 静态 mock
// 这样前端在网络中断 / API 不可用时仍可演示。

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''
const API_KEY = import.meta.env.VITE_API_KEY || ''
const TIMEOUT_MS = 10000

async function request(path, options = {}, timeoutMs = TIMEOUT_MS) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      ...options,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...(API_KEY ? { 'x-api-key': API_KEY } : {}),
        ...options.headers,
      },
    })
    clearTimeout(timer)
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`)
    return res.json()
  } catch (err) {
    clearTimeout(timer)
    throw err
  }
}

export async function fetchScenarios() {
  return request('/api/scenarios')
}

export async function fetchAnalysis(query) {
  const encoded = encodeURIComponent(query)
  return request(`/api/analyze?query=${encoded}`)
}

// 本地稳定副本（./public/data/cache.json），用于 API 不可达时降级
export async function fetchLocalCache() {
  const res = await fetch('/data/cache.json')
  if (!res.ok) throw new Error('local cache not found')
  const data = await res.json()
  return data.entries || data
}

// 一站式获取：先 API，失败后用本地副本，再失败回 null
export async function fetchAnalysisWithFallback(query) {
  try {
    return { source: 'api', data: await fetchAnalysis(query) }
  } catch (err) {
    console.warn('[api] API 不可达，尝试本地副本:', err.message)
    try {
      const cache = await fetchLocalCache()
      const entry = cache[query]
      if (!entry) throw new Error('query not in local cache')
      return { source: 'local', data: entry }
    } catch (err2) {
      console.warn('[api] 本地副本也失败:', err2.message)
      return { source: 'none', data: null }
    }
  }
}

// ============================================================
// Job API：创建任务、查询状态、SSE 订阅进度
// ============================================================

export async function startJob(query) {
  return request('/api/jobs', {
    method: 'POST',
    body: JSON.stringify({ query }),
  })
}

export async function getJob(jobId) {
  return request(`/api/jobs/${jobId}`)
}

export function subscribeJobEvents(jobId, onEvent) {
  const es = new EventSource(`${API_BASE}/api/jobs/${jobId}/events`)
  es.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      onEvent(data)
      if (data.stage === 'complete' || data.stage === 'failed') {
        es.close()
      }
    } catch (err) {
      console.warn('[sse] parse error', err)
    }
  }
  es.onerror = (err) => {
    console.warn('[sse] connection error', err)
  }
  return es
}

export async function fetchHistory() {
  return request('/api/history')
}

// ============================================================
// 可视化 API：用于三张看板（Executive / Supply / Risk）
// ============================================================

export async function fetchVisualize(page, query) {
  const q = query ? `?query=${encodeURIComponent(query)}` : ''
  return request(`/api/visualize/${page}${q}`)
}

export async function fetchExecutiveViz(query) {
  return fetchVisualize('executive', query)
}

export async function fetchSupplyViz(query) {
  return fetchVisualize('supply', query)
}

export async function fetchRiskViz(query) {
  return fetchVisualize('risk', query)
}
