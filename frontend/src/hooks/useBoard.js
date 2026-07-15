import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchBoard, normalizeBoardData, refreshBoard } from '../services/api'

// 三看板共用的数据状态机：打开只读缓存（404 → 空态），点「刷新分析」才重新跑编排
export function useBoard(page) {
  const [data, setData] = useState(null)
  // status: 'loading' | 'ready' | 'empty'(404 从未分析) | 'error'
  const [status, setStatus] = useState('loading')
  const [error, setError] = useState(null)
  const navigate = useNavigate()

  useEffect(() => {
    let mounted = true
    setStatus('loading')
    setError(null)
    setData(null)
    fetchBoard(page)
      .then((board) => {
        if (!mounted) return
        setData(normalizeBoardData(page, board))
        setStatus('ready')
      })
      .catch((err) => {
        if (!mounted) return
        if (err.status === 404) {
          setStatus('empty')
        } else {
          setError(err.message)
          setStatus('error')
        }
      })
    return () => {
      mounted = false
    }
  }, [page])

  // 触发刷新并跳进度页；返回 null 表示已跳转，否则返回要给用户看的错误文案
  const refresh = useCallback(async () => {
    try {
      const { job_id } = await refreshBoard(page)
      navigate(`/progress/${job_id}`)
      return null
    } catch (err) {
      if (err.status === 409) return '该看板已有分析任务进行中，请稍候'
      return err.message
    }
  }, [page, navigate])

  return { data, status, error, refresh }
}
