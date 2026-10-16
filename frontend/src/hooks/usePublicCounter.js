import { useEffect, useState } from 'react'
import { startCounterPolling } from '@/lib/live-counter.js'

export default function usePublicCounter() {
  const [snapshot, setSnapshot] = useState(null)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState(false)
  useEffect(() => {
    const poller = startCounterPolling({
      read: async (signal) => {
        const response = await fetch('/api/public/counter', { signal, cache: 'no-store' })
        if (!response.ok) throw new Error('Unable to load the community counter.')
        return response.json()
      },
      onData: (data) => { setSnapshot(data); setConnected(true); setError(false) },
      onError: () => { setConnected(false); setError(true) },
    })
    return () => poller.stop()
  }, [])
  return { snapshot, connected, error }
}
