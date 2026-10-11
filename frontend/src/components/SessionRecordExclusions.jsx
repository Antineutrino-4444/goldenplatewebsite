import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button.jsx'

export default function SessionRecordExclusions({ sessionId, onChanged }) {
  const [open, setOpen] = useState(false)
  const [records, setRecords] = useState([])
  const [filter, setFilter] = useState('issues')
  const [search, setSearch] = useState('')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const mounted = useRef(true)
  const pending = useRef(false)
  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false }
  }, [])

  const request = async (url, options) => {
    const response = await fetch(url, options)
    const data = await response.json()
    if (!response.ok) throw new Error(data.error || 'Unable to update session records.')
    return data
  }

  const expand = async () => {
    setOpen(!open)
    if (open || pending.current) return
    pending.current = true
    setBusy(true)
    setError('')
    try {
      const data = await request(`/api/session/${encodeURIComponent(sessionId)}/calculation-records`)
      if (mounted.current) setRecords(data.records)
    } catch (failure) {
      if (mounted.current) setError(failure.message)
    } finally {
      pending.current = false
      if (mounted.current) setBusy(false)
    }
  }

  const change = async (record) => {
    if (pending.current) return
    pending.current = true
    setBusy(true)
    setError('')
    setMessage('')
    try {
      const data = await request(`/api/session/${encodeURIComponent(sessionId)}/records/${encodeURIComponent(record.record_id)}/exclusion`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ excluded: !record.is_excluded, reason: reason.trim() || record.issue || '' }),
      })
      if (!mounted.current) return
      setRecords(data.records)
      setMessage(`${data.message}${data.reset_draw_session_ids.length ? ' Affected draw selections were cleared; draw logs are preserved.' : ''}`)
      await onChanged()
    } catch (failure) {
      if (mounted.current) setError(failure.message)
    } finally {
      pending.current = false
      if (mounted.current) setBusy(false)
    }
  }

  const visible = records.filter((record) => {
    const statusMatches = filter === 'all' || (filter === 'excluded' ? record.is_excluded : record.issue || record.is_excluded)
    return statusMatches && `${record.name} ${record.house} ${record.category}`.toLowerCase().includes(search.toLowerCase())
  })

  return <div className="mb-4 rounded-lg border bg-gray-50 p-3 space-y-3">
    <Button type="button" variant="outline" size="sm" onClick={expand} aria-expanded={open}>
      {open ? 'Hide record review' : 'Review or exclude records'}
    </Button>
    {open && <>
      <p className="text-sm text-gray-600">
        Exclude individual records from estimates, house scores, counts, clean rates, live totals, and draws.
        Linked students are also removed from this session’s estimation population. Original records are kept and can be restored.
        Affected draw selections are cleared and their logs are preserved.
      </p>
      <div className="flex flex-wrap gap-2">
        <label className="flex min-w-0 flex-wrap items-center gap-2 text-sm">Show
          <select aria-label="Filter calculation records" value={filter} onChange={(event) => setFilter(event.target.value)} className="max-w-full rounded border bg-white p-2">
            <option value="issues">Roster conflicts and exclusions</option>
            <option value="all">All records</option>
            <option value="excluded">Excluded records</option>
          </select>
        </label>
        <input aria-label="Search calculation records" placeholder="Search records" value={search}
          onChange={(event) => setSearch(event.target.value)} className="min-w-0 flex-1 rounded border p-2 text-sm" />
      </div>
      <label className="block text-sm">Reason (optional)
        <input value={reason} maxLength={1000} onChange={(event) => setReason(event.target.value)}
          className="mt-1 w-full rounded border p-2" placeholder="Why this record should be excluded" />
      </label>
      {busy && <p role="status" className="text-sm text-gray-500">Updating records…</p>}
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {message && <p role="status" className="text-sm text-teal-800">{message}</p>}
      {!busy && !error && !visible.length && <p className="text-sm text-gray-500">
        No matching records. Choose All records to review other entries.
      </p>}
      <ul className="max-h-96 space-y-2 overflow-y-auto">
        {visible.map((record) => <li key={record.record_id} className="flex flex-wrap items-start justify-between gap-3 rounded border bg-white p-3">
          <div className="min-w-0 flex-1 text-sm">
            <p className="font-medium break-words">{record.name}</p>
            <p className="text-xs text-gray-500">{record.category.toUpperCase()} • {record.house || (record.is_count_only ? 'Count only' : 'No house')} • {record.is_excluded ? 'Excluded' : 'Included'}</p>
            {record.issue && <p className="mt-1 text-xs text-amber-800">{record.issue}</p>}
            {record.is_excluded && record.exclusion_reason && <p className="mt-1 text-xs text-gray-600">Reason: {record.exclusion_reason}</p>}
          </div>
          <Button type="button" variant="outline" size="sm" disabled={busy} onClick={() => change(record)}>
            {record.is_excluded ? 'Restore record' : 'Exclude record'}
          </Button>
        </li>)}
      </ul>
    </>}
  </div>
}
