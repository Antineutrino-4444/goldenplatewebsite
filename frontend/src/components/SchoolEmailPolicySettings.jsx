import VideoHelp from '@/components/VideoHelp.jsx'
import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button.jsx'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog.jsx'
import { Label } from '@/components/ui/label.jsx'
import { Textarea } from '@/components/ui/textarea.jsx'

const entries = (value) => value.split(/[\s,;]+/).map((part) => part.trim()).filter(Boolean)

export default function SchoolEmailPolicySettings({ app, open, onOpenChange, onCloseAutoFocus }) {
  const [enabled, setEnabled] = useState(false)
  const [domains, setDomains] = useState('')
  const [exceptions, setExceptions] = useState('')
  const [busy, setBusy] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    if (!open) return
    let active = true
    setLoaded(false)
    setError('')
    fetch('/api/school/email-policy').then(async (response) => {
      const policy = await response.json()
      if (!active) return
      if (!response.ok) throw new Error(policy.error || 'Unable to load email rules.')
      setEnabled(policy.enabled)
      setDomains(policy.allowed_domains.join('\n'))
      setExceptions(policy.exceptions.join('\n'))
      setLoaded(true)
    }).catch((failure) => { if (active) setError(failure.message) })
    return () => { active = false }
  }, [open, app.user.id])

  const save = async (event) => {
    event.preventDefault()
    if (busy || !loaded) return
    setBusy(true)
    setError('')
    try {
      const response = await fetch('/api/school/email-policy', {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled, allowed_domains: entries(domains), exceptions: entries(exceptions) }),
      })
      const result = await response.json()
      if (!response.ok) throw new Error(result.error || 'Unable to save email rules.')
      app.showMessage('School email rules saved.', 'success')
      onOpenChange(false)
    } catch (failure) {
      setError(failure.message || 'Unable to connect. Please try again.')
    } finally { setBusy(false) }
  }

  return <Dialog open={open} onOpenChange={onOpenChange}>
    <DialogContent dismissOnOverlayClick={false} onCloseAutoFocus={onCloseAutoFocus}>
      <DialogHeader>
        <DialogTitle>School email rules</DialogTitle>
        <DialogDescription>Choose which email addresses can join {app.user.school?.name || 'your school'}. Exceptions still need a verification code.</DialogDescription>
      </DialogHeader>
      <VideoHelp videos={[21]} label="Watch: school email rules" />
      <form onSubmit={save} className="space-y-4">
        <label className="flex items-start gap-3 text-sm">
          <input type="checkbox" checked={enabled} disabled={!loaded || busy} onChange={(event) => setEnabled(event.target.checked)} className="mt-1 h-4 w-4 shrink-0 accent-amber-600" />
          <span>Require an approved email for school members</span>
        </label>
        <div className="space-y-2">
          <Label htmlFor="email-rule-domains">Allowed domains</Label>
          <Textarea id="email-rule-domains" value={domains} disabled={!loaded || busy} onChange={(event) => setDomains(event.target.value)} placeholder="school.edu" rows={3} aria-describedby="email-rule-domain-help" />
          <p id="email-rule-domain-help" className="text-sm text-muted-foreground">One domain per line. Add subdomains separately, such as students.school.edu.</p>
        </div>
        <div className="space-y-2">
          <Label htmlFor="email-rule-exceptions">Exceptions: email addresses or domains</Label>
          <Textarea id="email-rule-exceptions" value={exceptions} disabled={!loaded || busy} onChange={(event) => setExceptions(event.target.value)} placeholder={'coach@example.com\npartner.edu'} rows={3} aria-describedby="email-rule-exception-help" />
          <p id="email-rule-exception-help" className="text-sm text-muted-foreground">One address or domain per line. These are allowed even when they do not match an allowed domain.</p>
        </div>
        <p className="text-sm text-muted-foreground">When enabled, existing members must verify an acceptable email to continue or log out. Admins and superadmins are exempt.</p>
        {!loaded && !error && <p role="status" className="text-sm">Loading email rules…</p>}
        {error && <p role="alert" className="text-sm text-red-700 dark:text-red-300">{error}</p>}
        <div className="flex flex-wrap justify-end gap-2">
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>Close</Button>
          <Button type="submit" disabled={!loaded || busy}>{busy ? 'Saving…' : 'Save email rules'}</Button>
        </div>
      </form>
    </DialogContent>
  </Dialog>
}
