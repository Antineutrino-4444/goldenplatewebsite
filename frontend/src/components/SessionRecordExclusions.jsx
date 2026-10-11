import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button.jsx'

async function request(url, options) {
  const response = await fetch(url, options)
  const data = await response.json()
  if (!response.ok) throw new Error(data.error || 'Unable to update session records.')
  return data
}

export default function SessionRecordExclusions({ sessionId, onChanged, rosterScope = 'auto', reviewVersion = 0, onRosterScopeChange }) {
  const [open, setOpen] = useState(false)
  const [records, setRecords] = useState([])
  const [filter, setFilter] = useState('issues')
  const [search, setSearch] = useState('')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(false)
  const [rosterReview, setRosterReview] = useState(null)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const mounted = useRef(true)
  const pending = useRef(false)
  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false }
  }, [])

  useEffect(() => {
    if (!open) return
    let cancelled = false
    setLoading(true)
    setError('')
    request(`/api/session/${encodeURIComponent(sessionId)}/calculation-records?roster=${encodeURIComponent(rosterScope)}`)
      .then((data) => {
        if (cancelled) return
        setRecords(data.records)
        setRosterReview(data.roster_review)
      })
      .catch((failure) => { if (!cancelled) setError(failure.message) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [open, sessionId, rosterScope, reviewVersion])

  const change = async (record) => {
    if (pending.current || loading) return
    pending.current = true
    setBusy(true)
    setError('')
    setMessage('')
    try {
      const data = await request(`/api/session/${encodeURIComponent(sessionId)}/records/${encodeURIComponent(record.record_id)}/exclusion?roster=${encodeURIComponent(rosterScope)}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ excluded: !record.is_excluded, reason: reason.trim() || record.issue || '' }),
      })
      if (!mounted.current) return
      setRecords(data.records)
      setRosterReview(data.roster_review)
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
    <Button type="button" variant="outline" size="sm" onClick={() => setOpen(!open)} aria-expanded={open}>
      {open ? 'Hide record review' : 'Review or exclude records'}
    </Button>
    {open && <>
      <p className="text-sm text-gray-600">
        Exclude individual records from estimates, house scores, counts, clean rates, live totals, and draws.
        Linked students are also removed from this session’s estimation population. Original records are kept and can be restored.
        Affected draw selections are cleared and their logs are preserved.
      </p>
      {onRosterScopeChange && <label className="flex flex-wrap items-center gap-2 text-sm">Compare with
        <select aria-label="Roster for record review" value={rosterScope} disabled={busy}
          onChange={(event) => onRosterScopeChange(event.target.value)} className="max-w-full rounded border bg-white p-2">
          <option value="auto">Session roster</option>
          <option value="current">Current roster</option>
        </select>
      </label>}
      {!loading && rosterReview && <p className="text-sm text-gray-600">
        {rosterReview.available ? <>
          Checking {rosterReview.source === 'saved' ? 'this session’s saved roster' : 'the current roster'}{rosterReview.filename ? ` (${rosterReview.filename})` : ''}.
          {rosterReview.source === 'current' && <> {rosterReview.has_saved_roster
            ? 'The saved session roster stays unchanged during review.'
            : 'This session has no saved roster.'} After excluding conflicts, select Use current roster again to match the session.</>}
        </> : 'No student roster is available to check membership. Choose All records to review entries.'}
      </p>}
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
      {(busy || loading) && <p role="status" className="text-sm text-gray-500">{loading ? 'Checking records…' : 'Updating records…'}</p>}
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {message && <p role="status" className="text-sm text-teal-800">{message}</p>}
      {!busy && !loading && !error && !visible.length && <p className="text-sm text-gray-500">
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
          <Button type="button" variant="outline" size="sm" disabled={busy || loading} onClick={() => change(record)}>
            {record.is_excluded ? 'Restore record' : 'Exclude record'}
          </Button>
        </li>)}
      </ul>
    </>}
  </div>
}
