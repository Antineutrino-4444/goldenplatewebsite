import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button.jsx'
import LiveDeckConnections from '@/components/LiveDeckConnections.jsx'
import { readApiJson } from '@/lib/api-errors.js'

export default function AdminLiveDecks({ accountKey }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState(null)
  const [revision, setRevision] = useState(0)
  const action = useRef(null)
  useEffect(() => () => action.current?.abort(), [])

  useEffect(() => {
    const controller = new AbortController()
    let timer
    async function load() {
      try {
        const response = await fetch('/api/admin/presentations/live', { credentials: 'same-origin', cache: 'no-store', signal: controller.signal })
        const result = await readApiJson(response)
        if (!response.ok) throw new Error(result.error)
        if (controller.signal.aborted) return
        setData(result)
        setError('')
      } catch (failure) {
        if (!controller.signal.aborted) setError(failure.message || 'Couldn’t load connected presentations.')
      }
      if (!controller.signal.aborted) timer = setTimeout(load, 10000)
    }
    load()
    return () => { controller.abort(); clearTimeout(timer) }
  }, [accountKey, revision])

  async function sync(deck) {
    if (action.current) return
    const controller = new AbortController()
    action.current = controller
    setBusyId(deck.id)
    setError('')
    try {
      const response = await fetch('/api/admin/presentations/live/sync', {
        method: 'POST', credentials: 'same-origin', signal: controller.signal,
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ deck_id: deck.id }),
      })
      const result = await readApiJson(response)
      if (!response.ok) throw new Error(result.error)
      if (controller.signal.aborted) return
      setData(previous => ({ ...previous, connections: previous.connections.map(item =>
        item.id === deck.id ? { ...item, ...result.connection } : item) }))
      setRevision(value => value + 1)
    } catch (failure) {
      if (!controller.signal.aborted) setError(failure.message || 'Couldn’t request an update.')
    } finally {
      action.current = null
      if (!controller.signal.aborted) setBusyId(null)
    }
  }

  return <section className="admin-live-decks" aria-labelledby="admin-live-decks-title">
    <header><h3 id="admin-live-decks-title">Live assembly presentations</h3>
      <Button type="button" variant="outline" size="sm" onClick={() => setRevision(value => value + 1)}>Refresh status</Button></header>
    {!data && !error && <p className="live-deck-notice" role="status">Loading connections…</p>}
    {error && <p className="live-deck-notice" role="alert">{error}</p>}
    {data && <LiveDeckConnections connections={data.connections} providers={data.providers} onSync={sync} busyId={busyId} admin />}
  </section>
}
