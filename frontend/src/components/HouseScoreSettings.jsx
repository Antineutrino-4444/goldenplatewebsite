import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button.jsx'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { Input } from '@/components/ui/input.jsx'
import { Label } from '@/components/ui/label.jsx'

const fields = [
  ['clean_points', 'Clean plate reward'],
  ['dirty_penalty', 'Dirty plate deduction'],
  ['very_dirty_penalty', 'Very dirty plate deduction'],
]

export default function HouseScoreSettings({ app }) {
  const [settings, setSettings] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const saving = useRef(false)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const response = await fetch('/api/superadmin/house-score-settings')
        const data = await response.json()
        if (cancelled) return
        if (!response.ok) {
          setError(data.error || 'Unable to load house score settings.')
          return
        }
        setSettings(data.score_settings)
      } catch {
        if (!cancelled) setError('Unable to load house score settings. Reopen the panel to try again.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [app.user.school_id])

  const save = async (event) => {
    event.preventDefault()
    if (saving.current || !settings) return
    setError('')
    setMessage('')
    const values = Object.fromEntries(fields.map(([field]) => [field, Number(settings[field])]))
    if (fields.some(([field]) => settings[field] === '' || !Number.isInteger(values[field]) || values[field] < 0 || values[field] > 20)) {
      setError('Enter a whole number from 0 to 20 for every point value.')
      return
    }
    saving.current = true
    setBusy(true)
    try {
      const response = await fetch('/api/superadmin/house-score-settings', {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(values),
      })
      const data = await response.json()
      if (!response.ok) {
        setError(data.error || 'Unable to save house score settings.')
        return
      }
      setSettings(data.score_settings)
      setMessage('Saved. All existing session scores now use these values.')
      await app.loadHouseStats({ silent: false })
    } catch {
      setError('Unable to connect. Please try again.')
    } finally {
      saving.current = false
      setBusy(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>House score settings</CardTitle>
        <CardDescription>
          Choose whole numbers from 0 to 20 for your school. Changes recalculate all existing session scores.
          Count-only entries and records without a house earn no points.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {loading && <p className="text-sm text-gray-500">Loading score settings...</p>}
        {settings && <form onSubmit={save} className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            {fields.map(([field, label]) => (
              <div key={field} className="space-y-2">
                <Label htmlFor={`house-${field}`}>{label}</Label>
                <Input id={`house-${field}`} type="number" min={0} max={20} step={1} required
                  value={settings[field]} disabled={busy}
                  onChange={(event) => {
                    setSettings((current) => ({ ...current, [field]: event.target.value }))
                    setMessage('')
                  }} />
              </div>
            ))}
          </div>
          <Button type="submit" disabled={busy}>{busy ? 'Saving…' : 'Save point values'}</Button>
        </form>}
        {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
        {message && <p role="status" className="mt-3 text-sm text-emerald-700">{message}</p>}
      </CardContent>
    </Card>
  )
}
