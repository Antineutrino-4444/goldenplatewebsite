import { useCallback, useEffect, useRef, useState } from 'react'
import { startCounterPolling } from '@/lib/live-counter.js'

export default function useLiveCounter() {
  const [user, setUser] = useState(null)
  const [checkingAccess, setCheckingAccess] = useState(true)
  const [snapshot, setSnapshot] = useState(null)
  const [error, setError] = useState('')
  const [connected, setConnected] = useState(false)
  const poller = useRef(null)

  useEffect(() => {
    const controller = new AbortController()
    const check = async () => {
      try {
        const response = await fetch('/api/auth/status', { signal: controller.signal, cache: 'no-store' })
        if (!response.ok) throw new Error('Unable to check access. Please reload to try again.')
        const data = await response.json()
        if (!controller.signal.aborted) setUser(data.authenticated ? data.user : null)
      } catch (failure) {
        if (!controller.signal.aborted) setError(failure.message)
      } finally {
        if (!controller.signal.aborted) setCheckingAccess(false)
      }
    }
    check()
    return () => controller.abort()
  }, [])

  const identity = user ? `${user.school_id}:${user.role}:${user.id || 'guest'}` : ''
  useEffect(() => {
    if (!identity || user.role === 'inter_school') return
    setSnapshot(null)
    setConnected(false)
    setError('')
    const active = startCounterPolling({
      read: async (signal) => {
        const response = await fetch('/api/live-counter', { signal, cache: 'no-store' })
        const data = await response.json()
        if (!response.ok) {
          const failure = new Error(data.error || 'Unable to update the live counter.')
          failure.status = response.status
          throw failure
        }
        return data
      },
      onData: (data) => { setSnapshot(data); setConnected(true); setError('') },
      onError: (failure) => {
        setConnected(false)
        setError(failure.message || 'Connection interrupted. Retrying automatically.')
        if (failure.status === 401 || failure.status === 403) {
          setSnapshot(null)
          setUser(null)
          active.stop()
        }
      },
    })
    poller.current = active
    return () => { active.stop(); poller.current = null }
  }, [identity, user?.role])

  const refresh = useCallback(() => poller.current?.refresh(), [])
  const switchSchool = async () => {
    try {
      const response = await fetch('/api/auth/logout', { method: 'POST' })
      if (!response.ok) throw new Error('Unable to change school.')
      poller.current?.stop()
      setUser(null)
      setSnapshot(null)
      setError('')
      setConnected(false)
      return true
    } catch {
      setError('Unable to change school. Please try again.')
      return false
    }
  }
  return { user, setUser, checkingAccess, snapshot, error, setError, connected, refresh, switchSchool }
}
