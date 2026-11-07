import { useEffect, useRef, useState } from 'react'
import { readApiJson } from '../lib/api-errors.js'
import { Button } from '@/components/ui/button.jsx'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { Label } from '@/components/ui/label.jsx'
import { Switch } from '@/components/ui/switch.jsx'

export default function RecordingSettings({ app }) {
  const savedEnabled = app.user.school?.dirty_plate_name_input_enabled !== false
  const [enabled, setEnabled] = useState(savedEnabled)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const saving = useRef(false)

  useEffect(() => { setEnabled(savedEnabled) }, [savedEnabled])

  const save = async (event) => {
    event.preventDefault()
    if (saving.current) return
    saving.current = true
    setBusy(true)
    setError('')
    setMessage('')
    try {
      const response = await fetch('/api/superadmin/recording-settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dirty_plate_name_input_enabled: enabled }),
      })
      const data = await readApiJson(response)
      if (!response.ok) {
        setError(data.error || 'Unable to save recording settings.')
        return
      }
      app.setUser((current) => current?.school_id === app.user.school_id ? {
        ...current,
        school: { ...current.school, dirty_plate_name_input_enabled: data.dirty_plate_name_input_enabled },
      } : current)
      setMessage('Recording settings saved.')
    } catch {
      setError('Unable to connect. Please try again.')
    } finally {
      saving.current = false
      setBusy(false)
    }
  }

  return <Card>
    <CardHeader>
      <CardTitle>Plate recording</CardTitle>
      <CardDescription>Choose how your school records dirty plates.</CardDescription>
    </CardHeader>
    <CardContent>
      <form onSubmit={save} className="space-y-4">
        <div className="flex items-center justify-between gap-4">
          <div className="space-y-1">
            <Label htmlFor="dirty-plate-name-input">Dirty plate name input</Label>
            <p id="dirty-plate-name-description" className="text-sm text-gray-500">
              Turn off to add one unnamed dirty plate per click, with no input or confirmation dialog.
            </p>
          </div>
          <Switch id="dirty-plate-name-input" checked={enabled} disabled={busy}
            aria-describedby="dirty-plate-name-description"
            onCheckedChange={(value) => { setEnabled(value); setMessage('') }} />
        </div>
        <Button type="submit" disabled={busy || enabled === savedEnabled}>
          {busy ? 'Saving…' : 'Save recording settings'}
        </Button>
      </form>
      {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
      {message && <p role="status" className="mt-3 text-sm text-emerald-700">{message}</p>}
    </CardContent>
  </Card>
}
