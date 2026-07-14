import { useEffect, useRef, useState } from 'react'
import { getJob, subscribeJobEvents } from '../services/api'

export function useJob(jobId) {
  const [status, setStatus] = useState('pending')
  const [events, setEvents] = useState([])
  const [error, setError] = useState(null)
  const [job, setJob] = useState(null)
  const esRef = useRef(null)

  useEffect(() => {
    if (!jobId) return

    let mounted = true

    getJob(jobId)
      .then((data) => {
        if (!mounted) return
        setJob(data)
        setStatus(data.status)
      })
      .catch((err) => {
        if (!mounted) return
        setError(err.message)
      })

    esRef.current = subscribeJobEvents(jobId, (event) => {
      if (!mounted) return
      setEvents((prev) => [...prev, event])
      if (event.stage === 'complete' || event.stage === 'failed') {
        setStatus(event.stage)
        getJob(jobId).then(setJob).catch(console.error)
      }
    })

    return () => {
      mounted = false
      if (esRef.current) {
        esRef.current.close()
      }
    }
  }, [jobId])

  return { status, events, error, job }
}
