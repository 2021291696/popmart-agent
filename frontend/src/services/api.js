// API 客户端
// 看板数据采用两级策略：后端 visualize API → 本地预计算演示副本（public/data/cache.json）
// 这样后端不可达时，三个看板页对预设场景仍可离线演示。

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

export async function fetchHistory() {
  return request('/api/history')
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

// SSE 订阅任务进度。onError 在连接失败/断开时触发（EventSource 会自动重连，
// 由调用方决定是否降级为轮询）。注意 EventSource 无法携带 x-api-key，
// 认证开启时 SSE 会 401 → 调用方应走轮询降级并把认证错误暴露给用户。
export function subscribeJobEvents(jobId, onEvent, onError) {
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
    if (onError) onError(err)
  }
  return es
}

// ============================================================
// 可视化 API：用于三张看板（Executive / Supply / Risk）
// ============================================================

export async function fetchVisualize(page, query) {
  const q = query ? `?query=${encodeURIComponent(query)}` : ''
  return request(`/api/visualize/${page}${q}`)
}

// ============================================================
// 本地演示副本 + 形状归一化
// public/data/cache.json 结构：{ executive: {query: viz}, supply: {...}, risk: {...} }
// viz 与后端 visualize 响应同构（由 .demo_cache.json 预计算生成）。
// ============================================================

export async function fetchLocalVizCache() {
  const res = await fetch('/data/cache.json')
  if (!res.ok) throw new Error('local demo cache not found')
  return res.json()
}

// 统一 API / 本地副本两种来源的数据形状（后端 entry 可能缺 saved_at 等字段），
// 渲染层只面对归一化后的结构。
export function normalizeVizData(page, data) {
  if (!data || typeof data !== 'object') return data
  const base = {
    query: '',
    title: '',
    final_answer: '',
    generated_at: '',
    ...data,
  }
  if (page === 'executive') {
    return {
      ...base,
      agents: data.agents ?? [],
      total_agents: data.total_agents ?? data.agents?.length ?? 0,
      total_steps: data.total_steps ?? 0,
      total_llm_calls: data.total_llm_calls ?? 0,
      elapsed_seconds: data.elapsed_seconds ?? 0,
    }
  }
  if (page === 'supply') {
    return {
      ...base,
      agent: data.agent ?? null,
      tool_distribution: data.tool_distribution ?? [],
    }
  }
  if (page === 'risk') {
    return {
      ...base,
      agents: data.agents ?? [],
      conflicts: data.conflicts ?? [],
      total_rounds: data.total_rounds ?? 1,
      has_conflict: data.has_conflict ?? (data.conflicts?.length ?? 0) > 0,
    }
  }
  return base
}

// 一站式看板数据：先打后端 visualize API，失败时查本地演示副本。
// 返回 { source: 'api' | 'local', data }；都失败则抛原始 API 错误（页面显示错误卡）。
export async function fetchVisualizeWithFallback(page, query) {
  try {
    const data = await fetchVisualize(page, query)
    return { source: 'api', data: normalizeVizData(page, data) }
  } catch (err) {
    console.warn(`[api] visualize/${page} 请求失败，尝试本地演示副本:`, err.message)
    try {
      const cache = await fetchLocalVizCache()
      const hit = cache?.[page]?.[query] ?? null
      if (!hit) throw new Error('query not in local demo cache')
      return { source: 'local', data: normalizeVizData(page, hit) }
    } catch (err2) {
      console.warn('[api] 本地演示副本未命中:', err2.message)
      throw err
    }
  }
}
