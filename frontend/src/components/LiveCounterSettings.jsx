import { useRef, useState } from 'react'
import { Button } from '@/components/ui/button.jsx'
import { DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog.jsx'
import { Input } from '@/components/ui/input.jsx'
import { Label } from '@/components/ui/label.jsx'
import { rangeLabel } from '@/lib/live-counter.js'

const zones = [
  ['America/New_York', 'Eastern Time'], ['America/Chicago', 'Central Time'],
  ['America/Denver', 'Mountain Time'], ['America/Los_Angeles', 'Pacific Time'],
  ['America/Halifax', 'Atlantic Time'], ['America/St_Johns', 'Newfoundland Time'],
  ['Europe/London', 'London'], ['Europe/Paris', 'Paris'], ['Asia/Shanghai', 'China'],
  ['Asia/Tokyo', 'Japan'], ['Australia/Sydney', 'Sydney'], ['UTC', 'UTC'],
]
const selectClass = 'h-10 w-full min-w-0 rounded-md border border-slate-200 bg-white px-3 text-sm'

export default function LiveCounterSettings({ settings, canSetDefault, onSaved }) {
  const [year, setYear] = useState(settings.year)
  const [timezone, setTimezone] = useState(settings.timezone)
  const [defaultRange, setDefaultRange] = useState(settings.default_range)
  const [milestone, setMilestone] = useState(settings.milestone ?? '')
  const [ranges, setRanges] = useState(Array.from({ length: 3 }, (_, index) => {
    const id = `custom-${index + 1}`
    return { id, name: '', start_date: '', end_date: '',
      ...settings.custom_ranges.find((range) => range.id === id) }
  }))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const saving = useRef(false)
  const update = (index, field, value) => setRanges((current) => current.map((range, i) =>
    i === index ? { ...range, [field]: value } : range))
  const filledRanges = ranges.filter((range) => range.start_date && range.end_date)

  const save = async (event) => {
    event.preventDefault()
    if (saving.current) return
    setError('')
    const customRanges = ranges.filter((range) => range.start_date || range.end_date || range.name.trim())
    if (customRanges.some((range) => !range.start_date || !range.end_date || range.start_date > range.end_date)) {
      setError('Each custom range needs a start date and an end date on or after it.')
      return
    }
    saving.current = true
    setBusy(true)
    try {
      const response = await fetch('/api/live-counter/settings', {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ year: Number(year), timezone, custom_ranges: customRanges,
          ...(canSetDefault ? { default_range: defaultRange, milestone: milestone === '' ? null : Number(milestone) } : {}) }),
      })
      const result = await response.json()
      if (!response.ok) { setError(result.error || 'Unable to save date ranges.'); return }
      onSaved()
    } catch {
      setError('Unable to connect. Please try again.')
    } finally {
      saving.current = false
      setBusy(false)
    }
  }

  return <>
    <DialogHeader>
      <DialogTitle>Manage time ranges</DialogTitle>
      <DialogDescription>
        Set the calendar year and up to three custom ranges for your school. Both dates are included.
        Custom names are optional. Leave a range blank to omit it.
      </DialogDescription>
    </DialogHeader>
    <form onSubmit={save} className="space-y-5">
      <fieldset disabled={busy} className="space-y-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2"><Label htmlFor="counter-year">Calendar year</Label>
            <Input id="counter-year" type="number" required min={1900} max={9998} step={1}
              value={year} onChange={(event) => setYear(event.target.value)} /></div>
          <div className="space-y-2"><Label htmlFor="counter-timezone">Reporting timezone</Label>
            <select id="counter-timezone" className={selectClass} value={timezone} onChange={(event) => setTimezone(event.target.value)}>
              {!zones.some(([value]) => value === timezone) && <option value={timezone}>{timezone}</option>}
              {zones.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select></div>
        </div>
        {ranges.map((range, index) => <div key={range.id} className="rounded-xl border border-slate-200 p-4 space-y-3">
          <div className="flex items-center justify-between gap-2">
            <h3 className="font-semibold text-slate-800">Custom range {index + 1}</h3>
            <Button type="button" size="sm" variant="ghost" onClick={() => setRanges((current) => current.map((item, i) =>
              i === index ? { ...item, name: '', start_date: '', end_date: '' } : item))}>Clear range {index + 1}</Button>
          </div>
          <div className="space-y-2"><Label htmlFor={`${range.id}-name`}>Name (optional)</Label>
            <Input id={`${range.id}-name`} maxLength={80} placeholder="e.g. Fall term" value={range.name}
              onChange={(event) => update(index, 'name', event.target.value)} /></div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-2"><Label htmlFor={`${range.id}-start`}>Start date</Label>
              <Input id={`${range.id}-start`} type="date" min="1900-01-01" max="9998-12-31" value={range.start_date}
                onChange={(event) => update(index, 'start_date', event.target.value)} /></div>
            <div className="space-y-2"><Label htmlFor={`${range.id}-end`}>End date</Label>
              <Input id={`${range.id}-end`} type="date" min={range.start_date || '1900-01-01'} max="9998-12-31" value={range.end_date}
                onChange={(event) => update(index, 'end_date', event.target.value)} /></div>
          </div>
        </div>)}
        {canSetDefault ? <div className="space-y-2"><Label htmlFor="counter-default-range">Default time range</Label>
          <select id="counter-default-range" className={selectClass} value={defaultRange} onChange={(event) => setDefaultRange(event.target.value)}>
            <option value="year">Calendar year {year}</option>
            {filledRanges.map((range) => <option key={range.id} value={range.id}>{rangeLabel(range)}</option>)}
            {defaultRange !== 'year' && !filledRanges.some((range) => range.id === defaultRange)
              && <option value={defaultRange} disabled>Choose a saved default range</option>}
          </select></div> : <p className="text-sm text-slate-500">Only superadmins can change the default time range and celebration milestone.</p>}
        {canSetDefault && <div className="space-y-2">
          <Label htmlFor="counter-milestone">Celebration milestone (clean plates)</Label>
          <Input id="counter-milestone" type="number" min={1} max={1000000000} step={1}
            placeholder="e.g. 1000" value={milestone} onChange={(event) => setMilestone(event.target.value)} />
          <p className="text-xs leading-relaxed text-slate-500">Celebrate when the selected range reaches this many clean plates. Leave blank to turn celebrations off. The goal applies only to your school.</p>
        </div>}
        <p className="text-sm text-slate-500">The counter always includes both student and faculty plates.</p>
      </fieldset>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      <Button type="submit" disabled={busy}>{busy ? 'Saving…' : 'Save time ranges'}</Button>
    </form>
  </>
}
