import { useEffect, useId, useRef, useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { Button } from '@/components/ui/button.jsx'

export default function MatchSessionRoster({ sessionId, loading, onMatched, onMatchFailed, calculationRevision }) {
  const [open, setOpen] = useState(false)
  const contentId = useId()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const pending = useRef(false)
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false }
  }, [])
  useEffect(() => {
    setError('')
    setMessage('')
  }, [calculationRevision])

  const match = async () => {
    if (pending.current || !sessionId) return
    pending.current = true
    setBusy(true)
    setError('')
    setMessage('')
    try {
      const response = await fetch(`/api/session/${encodeURIComponent(sessionId)}/roster/current`, { method: 'POST' })
      const data = await response.json()
      if (!mounted.current) return
      if (!response.ok) {
        setError(data.error || 'Unable to match this session to the current roster.')
        onMatchFailed?.()
        return
      }
      setMessage(`Matched to ${data.estimation.roster_filename || 'the current roster'} (${data.estimation.population} students).`)
      await onMatched()
    } catch {
      if (mounted.current) setError('Unable to connect. Please try again.')
    } finally {
      pending.current = false
      if (mounted.current) setBusy(false)
    }
  }

  return (
    <div className="mb-4 rounded-lg border bg-gray-50 p-3 space-y-2">
      <Button type="button" size="sm" variant="outline" onClick={() => setOpen(!open)}
        aria-expanded={open} aria-controls={contentId}>
        {open ? 'Hide roster matching' : 'Match session roster'}
        <ChevronDown className={`h-4 w-4 transition-transform ${open ? 'rotate-180' : ''}`} />
      </Button>
      <div id={contentId} hidden={!open} className="space-y-2">
        <p className="text-sm text-gray-600">
          If the current student roster belongs to this session, match it here to recalculate its estimates.
          This saves the roster for this session.
        </p>
        <Button type="button" size="sm" variant="outline" disabled={busy || loading} onClick={match}>
          {busy ? 'Matching roster…' : 'Use current roster'}
        </Button>
        {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
        {message && <p role="status" className="text-sm text-teal-800">{message}</p>}
      </div>
    </div>
  )
}
