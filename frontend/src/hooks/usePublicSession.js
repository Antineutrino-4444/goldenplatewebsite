import { useEffect, useState } from 'react'

export function usePublicSession(sessionId) {
  const [attempt, setAttempt] = useState(0)
  const [result, setResult] = useState({ status: 'loading', session: null })
  useEffect(() => {
    const controller = new AbortController()
    let active = true
    setResult({ status: 'loading', session: null })
    const timeout = setTimeout(() => controller.abort(), 10000)
    const path = sessionId ? encodeURIComponent(sessionId) : 'random'
    fetch(`/api/public/sessions/${path}`, { signal: controller.signal, cache: 'no-store' })
      .then(async (response) => {
        if (!response.ok) throw new Error(response.status === 404 ? 'unavailable' : 'error')
        return response.json()
      })
      .then((data) => {
        if (active) setResult({ status: data.session ? 'ready' : 'empty', session: data.session })
      })
      .catch((error) => {
        if (active) setResult({ status: error.message === 'unavailable' ? 'unavailable' : 'error', session: null })
      })
      .finally(() => clearTimeout(timeout))
    return () => { active = false; controller.abort(); clearTimeout(timeout) }
  }, [sessionId, attempt])
  return { ...result, retry: () => setAttempt((value) => value + 1) }
}
