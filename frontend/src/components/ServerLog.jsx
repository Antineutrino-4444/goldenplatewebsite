import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button.jsx'
import { Input } from '@/components/ui/input.jsx'
import { readApiJson } from '../lib/api-errors.js'
import { startCounterPolling } from '../lib/live-counter.js'

const LOG_URL = '/api/interschool/server-log'
const UPDATE_INTERVAL_MS = 3000
const eventTime = new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', second: '2-digit' })

export default function ServerLog() {
  const [entries, setEntries] = useState([])
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')
  const [failures, setFailures] = useState(false)
  const [loading, setLoading] = useState(true)
  const [paused, setPaused] = useState(false)
  const [following, setFollowing] = useState(true)
  const pauseRef = useRef(false)
  const followRef = useRef(true)
  const viewerOpened = useRef(false)
  const list = useRef(null)
  const poller = useRef(null)

  const filters = new URLSearchParams({ search: query, failures: failures ? '1' : '0' }).toString()
  const exportParams = new URLSearchParams({ search: search.trim(), failures: failures ? '1' : '0', format: 'csv' })

  useEffect(() => {
    const timer = setTimeout(() => setQuery(search.trim()), 250)
    return () => clearTimeout(timer)
  }, [search])

  useEffect(() => {
    let first = true
    let cursor = 0
    setLoading(true)
    setEntries([])
    followRef.current = true
    setFollowing(true)

    const active = startCounterPolling({
      interval: UPDATE_INTERVAL_MS,
      read: async (signal) => {
        if (!first && pauseRef.current) return null
        const poll = viewerOpened.current ? '1' : '0'
        viewerOpened.current = true
        const response = await fetch(`${LOG_URL}?${filters}&after=${cursor}&poll=${poll}`, { signal })
        const data = await readApiJson(response)
        if (!response.ok) {
          const failure = new Error(data.error)
          failure.status = response.status
          throw failure
        }
        return data
      },
      onData: (data) => {
        if (!data || (!first && pauseRef.current)) return
        const replace = first || data.reset
        cursor = data.cursor
        first = false
        setLoading(false)
        setError('')
        if (replace || data.entries.length) {
          setEntries((current) => replace ? data.entries : [...current, ...data.entries].slice(-data.limit))
        }
      },
      onError: (failure) => {
        setError(failure.message || 'Could not update the server log.')
        setLoading(false)
        if (failure.status === 401 || failure.status === 403) active.stop()
      },
    })
    poller.current = active
    return () => active.stop()
  }, [filters])

  useEffect(() => {
    if (followRef.current && list.current) list.current.scrollTop = list.current.scrollHeight
  }, [entries])

  function togglePause() {
    const next = !paused
    pauseRef.current = next
    setPaused(next)
    if (!next) poller.current?.refresh()
  }

  function trackScroll() {
    const element = list.current
    const atEnd = element.scrollHeight - element.scrollTop - element.clientHeight <= 24
    followRef.current = atEnd
    setFollowing(atEnd)
  }

  function jumpToLatest() {
    list.current.scrollTop = list.current.scrollHeight
    followRef.current = true
    setFollowing(true)
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-2">
        <div className="w-full min-w-0 sm:max-w-sm sm:flex-1">
          <label htmlFor="server-log-search" className="mb-1 block text-sm font-medium">Find an action</label>
          <Input id="server-log-search" type="search" maxLength={160} placeholder="Account, route, or reference" value={search} onChange={(event) => setSearch(event.target.value)} />
        </div>
        <Button variant="outline" size="sm" onClick={togglePause}>{paused ? 'Resume live' : 'Pause'}</Button>
        <Button asChild variant="outline" size="sm"><a href={`${LOG_URL}?${exportParams}`}>Export CSV</a></Button>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 text-sm">
        <label className="flex min-h-8 items-center gap-2">
          <input type="checkbox" checked={failures} onChange={(event) => setFailures(event.target.checked)} className="accent-amber-700" />
          Failures only
        </label>
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground" role="status">{paused ? 'Paused' : error ? 'Update interrupted' : loading ? 'Loading…' : 'Live · updates every 3 seconds'}</span>
          {!following && <Button variant="outline" size="sm" onClick={jumpToLatest}>Jump to latest</Button>}
        </div>
      </div>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      {!loading && !error && !entries.length && <p className="text-sm text-muted-foreground">No matching actions in the last 30 days.</p>}
      <ol ref={list} onScroll={trackScroll} tabIndex={entries.length ? 0 : undefined} className="max-h-[28rem] divide-y overflow-y-auto border-t focus-visible:outline-2 focus-visible:outline-amber-600" aria-label="Server activity, oldest to newest">
        {entries.map((entry) => (
          <li key={entry.id} className="grid min-w-0 gap-1 px-1 py-2.5 text-sm sm:grid-cols-[11rem_minmax(0,1fr)] sm:gap-x-5">
            <div>
              <time dateTime={entry.occurred_at} className="block text-muted-foreground">{eventTime.format(new Date(entry.occurred_at))}</time>
              <div className="flex flex-wrap items-baseline gap-x-2">
                <span className="font-medium">{entry.actor || 'Unknown account'}</span>
                {entry.actor === 'Guest' && entry.actor_id && <span className="font-mono text-xs">{entry.actor_id}</span>}
                {entry.school && <span className="text-muted-foreground">{entry.school}</span>}
              </div>
            </div>
            <div className="min-w-0">
              <div className="font-mono">
                <span className={entry.status >= 400 ? 'font-semibold text-destructive' : 'font-semibold'}>{entry.status}</span>
                {' '}{entry.method} {entry.route}
              </div>
              <div className="text-xs text-muted-foreground">
                {[entry.elapsed_ms === 0 ? '<1 ms' : entry.elapsed_ms !== null && `${entry.elapsed_ms} ms`, entry.code, entry.reference && `Ref ${entry.reference}`, entry.detail].filter(Boolean).join(' · ')}
              </div>
            </div>
          </li>
        ))}
      </ol>
    </div>
  )
}
