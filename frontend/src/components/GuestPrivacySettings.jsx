import VideoHelp from '@/components/VideoHelp.jsx'
import { useEffect, useRef, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { Label } from '@/components/ui/label.jsx'
import { Switch } from '@/components/ui/switch.jsx'

export default function GuestPrivacySettings({ app }) {
  const [enabled, setEnabled] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const saving = useRef(false)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const response = await fetch('/api/admin/guest-privacy')
        const data = await response.json()
        if (cancelled) return
        if (!response.ok) throw new Error(data.error || 'Unable to load guest privacy.')
        setEnabled(data.enabled)
      } catch (failure) {
        if (!cancelled) setError(failure.message || 'Unable to load guest privacy. Reopen the panel to try again.')
      }
    }
    load()
    return () => { cancelled = true }
  }, [app.user.school_id])

  const save = async (next) => {
    if (saving.current) return
    saving.current = true
    setBusy(true)
    setError('')
    setMessage('')
    try {
      const response = await fetch('/api/admin/guest-privacy', {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: next }),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.error || 'Unable to save guest privacy.')
      setEnabled(data.enabled)
      setMessage(data.enabled ? 'Saved. Guest views now use anonymous student labels.' : 'Saved. Guest views now show original student details.')
    } catch (failure) {
      setError(failure.message || 'Unable to connect. Please try again.')
    } finally {
      saving.current = false
      setBusy(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Guest privacy</CardTitle>
        <CardDescription>
          Show guests unique labels such as Student 1 and Student 2 in records and draws.
          Each student keeps the same label across sessions. Personal IDs, grade and advisor details,
          individual house and clan details, staff names, notes, and session titles are hidden.
          Signed-in school accounts keep their normal view.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <VideoHelp videos={[25]} label="Watch: share guest views safely" />
        <div className="flex items-center justify-between gap-4">
          <Label htmlFor="guest-privacy">Anonymize student details for guests</Label>
          <Switch id="guest-privacy" checked={enabled === true} disabled={enabled === null || busy}
            onCheckedChange={save} />
        </div>
        {enabled === null && !error && <p className="text-sm text-gray-500">Loading guest privacy…</p>}
        {busy && <p className="text-sm text-gray-500" role="status">Saving…</p>}
        {error && <p className="text-sm text-red-700" role="alert">{error}</p>}
        {message && <p className="text-sm text-green-700" role="status">{message}</p>}
      </CardContent>
    </Card>
  )
}
