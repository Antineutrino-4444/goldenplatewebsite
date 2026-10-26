import VideoHelp from '@/components/VideoHelp.jsx'
import { useEffect, useState } from 'react'
import { Download, RefreshCcw } from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert.jsx'
import { Badge } from '@/components/ui/badge.jsx'
import { Button } from '@/components/ui/button.jsx'
import { Checkbox } from '@/components/ui/checkbox.jsx'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog.jsx'

export default function AdminSessionExport({ open, onOpenChange, accountKey }) {
  const [sessions, setSessions] = useState([])
  const [columns, setColumns] = useState([])
  const [selectedIds, setSelectedIds] = useState(new Set())
  const [anonymized, setAnonymized] = useState(new Set())
  const [excludeDiscarded, setExcludeDiscarded] = useState(false)
  const [format, setFormat] = useState('csv')
  const [loading, setLoading] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [reload, setReload] = useState(0)

  useEffect(() => {
    if (!open) return
    const controller = new AbortController()
    setLoading(true)
    setError('')
    setMessage('')
    setSessions([])
    setSelectedIds(new Set())
    setAnonymized(new Set())
    setExcludeDiscarded(false)
    setFormat('csv')
    const load = async () => {
      try {
        const response = await fetch('/api/admin/sessions/export', { signal: controller.signal })
        const data = await response.json()
        if (!response.ok) throw new Error(data.error || 'Could not load sessions')
        setSessions(data.sessions)
        setColumns(data.columns)
        setSelectedIds(new Set(data.sessions.map((item) => item.session_id)))
      } catch (failure) {
        if (!controller.signal.aborted) setError(failure.message || 'Could not load sessions')
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    }
    load()
    return () => controller.abort()
  }, [open, accountKey, reload])

  const eligible = sessions.filter((item) => !excludeDiscarded || !item.is_discarded)
  const selected = eligible.filter((item) => selectedIds.has(item.session_id))
  const recordCount = selected.reduce((total, item) => total + item.record_count, 0)
  const toggle = (setter, key, checked) => setter((previous) => {
    const next = new Set(previous)
    if (checked) next.add(key)
    else next.delete(key)
    return next
  })

  const download = async () => {
    if (!selected.length || exporting) return
    setExporting(true)
    setError('')
    setMessage('')
    try {
      const response = await fetch('/api/admin/sessions/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_ids: selected.map((item) => item.session_id),
          exclude_discarded: excludeDiscarded,
          anonymize_columns: [...anonymized],
          format,
        }),
      })
      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.error || 'Could not export records')
      }
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `all_sessions_detailed_records.${format}`
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
      const totalRecords = Number(response.headers.get('X-Export-Record-Count'))
      const totalSessions = Number(response.headers.get('X-Export-Session-Count'))
      setMessage(`Exported ${totalRecords} ${totalRecords === 1 ? 'record' : 'records'} from ${totalSessions} ${totalSessions === 1 ? 'session' : 'sessions'}.`)
    } catch (failure) {
      setError(failure.message || 'Could not export records')
    } finally {
      setExporting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[85dvh] flex-col overflow-hidden sm:max-w-2xl lg:max-w-3xl" dismissOnOverlayClick={false}>
        <DialogHeader className="shrink-0">
          <DialogTitle>Export All Sessions</DialogTitle>
          <DialogDescription>Export detailed records for the sessions you choose from your school.</DialogDescription>
        </DialogHeader>
        <div className="min-h-0 space-y-5 overflow-y-auto px-1">
          <VideoHelp videos={[16]} label="Watch: export multiple sessions" />
          {error && <Alert variant="destructive"><AlertDescription role="alert">{error}</AlertDescription></Alert>}
          {message && <p role="status" className="rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-800">{message}</p>}
          {loading ? <p role="status" className="py-8 text-center text-gray-500">Loading sessions…</p> : <>
            <fieldset className="space-y-3">
              <legend className="font-semibold">Export format</legend>
              <div className="grid gap-2 sm:grid-cols-2">
                <label className="flex cursor-pointer items-start gap-3 rounded-lg border p-3 text-sm">
                  <input type="radio" name="session-export-format" value="csv" checked={format === 'csv'} disabled={exporting} onChange={() => setFormat('csv')} className="mt-1" />
                  <span><span className="block font-medium">One CSV with session sections</span><span className="text-xs text-gray-500">Each session gets its own heading and record table.</span></span>
                </label>
                <label className="flex cursor-pointer items-start gap-3 rounded-lg border p-3 text-sm">
                  <input type="radio" name="session-export-format" value="zip" checked={format === 'zip'} disabled={exporting} onChange={() => setFormat('zip')} className="mt-1" />
                  <span><span className="block font-medium">ZIP with one CSV per session</span><span className="text-xs text-gray-500">Includes a separate CSV even for an empty session.</span></span>
                </label>
              </div>
            </fieldset>
            <section className="space-y-3" aria-labelledby="export-sessions-heading">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 id="export-sessions-heading" className="font-semibold">Choose sessions</h3>
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" variant="outline" disabled={exporting} onClick={() => setSelectedIds(new Set(eligible.map((item) => item.session_id)))}>Select all</Button>
                  <Button size="sm" variant="outline" disabled={exporting} onClick={() => setSelectedIds(new Set())}>Select none</Button>
                  <Button size="sm" variant="ghost" disabled={exporting} onClick={() => setReload((value) => value + 1)} aria-label="Refresh export sessions"><RefreshCcw className="h-4 w-4" /></Button>
                </div>
              </div>
              <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm">
                <Checkbox checked={excludeDiscarded} disabled={exporting} onCheckedChange={(checked) => setExcludeDiscarded(checked === true)} />
                Exclude all discarded sessions
              </label>
              <div className="max-h-56 space-y-2 overflow-y-auto rounded-lg border p-2">
                {!sessions.length && <p className="p-3 text-sm text-gray-500">No sessions are available to export.</p>}
                {sessions.map((item) => {
                  const excluded = excludeDiscarded && item.is_discarded
                  return <label key={item.session_id} className={`flex items-start gap-3 rounded-md border p-3 ${excluded ? 'bg-gray-50 text-gray-400' : 'cursor-pointer'}`}>
                    <Checkbox className="mt-1" aria-label={`Include ${item.session_name}`} checked={!excluded && selectedIds.has(item.session_id)} disabled={excluded || exporting} onCheckedChange={(checked) => toggle(setSelectedIds, item.session_id, checked === true)} />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2 font-medium [overflow-wrap:anywhere]">{item.session_name}{item.is_discarded && <Badge variant="secondary">Discarded</Badge>}</div>
                      <p className="text-xs text-gray-500">Owner: {item.owner} · {item.record_count.toLocaleString()} records{excluded ? ' · Excluded' : ''}</p>
                    </div>
                  </label>
                })}
              </div>
            </section>

            <section className="space-y-3" aria-labelledby="export-anonymize-heading">
              <h3 id="export-anonymize-heading" className="font-semibold">Anonymize columns</h3>
              <p className="text-sm text-gray-600">Exports use details saved with each record. Roster Status marks students missing from the current roster; House Changed and Roster Notes flag roster differences and matching conflicts.</p>
              <p className="text-sm text-gray-600">Choose which columns to anonymize. Consistent labels and a Person column help you follow each student across sessions within this download. New exports use new labels.</p>
              <div className="flex flex-wrap gap-2">
                <Button size="sm" variant="outline" disabled={exporting} onClick={() => setAnonymized(new Set(['Preferred', 'Last', 'Student ID']))}>Anonymize identities</Button>
                <Button size="sm" variant="outline" disabled={exporting} onClick={() => setAnonymized(new Set(columns.map((column) => column.key)))}>Anonymize all columns</Button>
                <Button size="sm" variant="outline" disabled={exporting} onClick={() => setAnonymized(new Set())}>Keep all readable</Button>
              </div>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {columns.map((column) => <label key={column.key} className="flex cursor-pointer items-center gap-2 rounded-md border p-3 text-sm">
                  <Checkbox aria-label={`Anonymize ${column.label.toLowerCase()}`} checked={anonymized.has(column.key)} disabled={exporting} onCheckedChange={(checked) => toggle(setAnonymized, column.key, checked === true)} />
                  {column.label}
                </label>)}
              </div>
              <p className="text-xs text-gray-500">Readable columns may identify students. Anonymizing this download leaves stored records unchanged. Excluded records are left out; merged sessions export their own records only.</p>
            </section>
          </>}
        </div>
        <div className="shrink-0 space-y-3 border-t pt-3">
          <p className="text-sm text-gray-600" role="status">{selected.length} of {sessions.length} sessions selected · {recordCount.toLocaleString()} records · {anonymized.size} columns anonymized</p>
          <div className="flex flex-wrap gap-2">
            <Button className="min-w-0 flex-1 bg-amber-600 hover:bg-amber-700" disabled={loading || exporting || !selected.length} onClick={download}><Download className="mr-2 h-4 w-4" />{exporting ? 'Exporting…' : 'Export Detailed Record List'}</Button>
            <Button variant="outline" onClick={() => onOpenChange(false)}>Close</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
