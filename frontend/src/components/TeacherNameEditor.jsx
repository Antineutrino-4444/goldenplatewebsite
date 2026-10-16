import { useState } from 'react'
import { Button } from '@/components/ui/button.jsx'
import { Input } from '@/components/ui/input.jsx'

export default function TeacherNameEditor({ teacher, save }) {
  const [editing, setEditing] = useState(false)
  const [preferred, setPreferred] = useState('')
  const [last, setLast] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  if (!editing) return (
    <div>
      <span>{teacher.display_name || teacher.name}</span>
      {teacher.faculty_identifier && <div className="text-xs text-muted-foreground">Faculty ID: {teacher.faculty_identifier}</div>}
      <Button variant="ghost" size="sm" onClick={() => {
        setPreferred(teacher.preferred_name || '')
        setLast(teacher.last_name || '')
        setError('')
        setEditing(true)
      }} aria-label={`Edit name for ${teacher.display_name || teacher.name}`}>Edit name</Button>
    </div>
  )

  return (
    <form className="space-y-2" onSubmit={async (event) => {
      event.preventDefault()
      setBusy(true)
      setError('')
      try {
        await save(teacher.teacher_id, { preferred_name: preferred, last_name: last })
        setEditing(false)
      } catch (failure) {
        setError(failure.message || 'Unable to save name.')
      } finally {
        setBusy(false)
      }
    }}>
      <label className="block">First / preferred name<Input value={preferred} onChange={event => setPreferred(event.target.value)} required disabled={busy} /></label>
      <label className="block">Last name<Input value={last} onChange={event => setLast(event.target.value)} required disabled={busy} /></label>
      <p className="text-xs text-muted-foreground">Past records and draw results display the updated name. The original recorded name is kept.</p>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      <div className="flex flex-wrap gap-2">
        <Button size="sm" type="submit" disabled={busy}>{busy ? 'Saving…' : 'Save name'}</Button>
        <Button size="sm" type="button" variant="outline" disabled={busy} onClick={() => setEditing(false)}>Cancel</Button>
      </div>
    </form>
  )
}
