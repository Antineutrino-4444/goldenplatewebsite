import { useRef, useState } from 'react'
import { Mail } from 'lucide-react'
import { Button } from '@/components/ui/button.jsx'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog.jsx'
import { Input } from '@/components/ui/input.jsx'
import { Label } from '@/components/ui/label.jsx'

export default function SchoolContactSettings({ app, open: controlledOpen, onOpenChange, hideTrigger = false, onCloseAutoFocus }) {
  const { user } = app
  const [internalOpen, setInternalOpen] = useState(!user.school_contact_email)
  const open = controlledOpen ?? internalOpen
  const setOpen = onOpenChange || setInternalOpen
  const [email, setEmail] = useState(user.school_contact_email || '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const saving = useRef(false)

  const save = async (event) => {
    event.preventDefault()
    if (saving.current) return
    saving.current = true
    setBusy(true)
    setError('')
    try {
      const response = await fetch('/api/school/contact-email', {
        method: 'PUT', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim() }),
      })
      const result = await response.json()
      if (!response.ok) {
        setError(result.error || 'Unable to save the contact email.')
        return
      }
      app.setUser((current) => current?.id === user.id ? {
        ...current, school_contact_email: result.contact_email,
        school_contact_email_required: false,
      } : current)
      setEmail(result.contact_email)
      setOpen(false)
    } catch {
      setError('Unable to connect. Please try again.')
    } finally {
      saving.current = false
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => {
      setOpen(next)
      if (next) {
        setEmail(user.school_contact_email || '')
        setError('')
      }
    }}>
      {!hideTrigger && <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="gap-2">
          <Mail className="h-4 w-4" aria-hidden="true" />School email
        </Button>
      </DialogTrigger>}
      <DialogContent dismissOnOverlayClick={false} onCloseAutoFocus={onCloseAutoFocus}>
        <DialogHeader>
          <DialogTitle>{user.school_contact_email ? 'School contact email' : 'Add a school contact email'}</DialogTitle>
          <DialogDescription>
            {user.school_contact_email ? '' : 'Your school does not have a contact email yet. '}
            Add an address to receive alerts when someone requests an account at your school
            or joins using an invite code.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={save} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="school-contact-email">Contact email</Label>
            <Input id="school-contact-email" type="email" autoComplete="email"
              required maxLength={320} value={email} disabled={busy}
              onChange={(event) => setEmail(event.target.value)} placeholder="school@example.com" />
          </div>
          {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>Close</Button>
            <Button type="submit" disabled={busy}>{busy ? 'Saving…' : 'Save contact email'}</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
