import { useState } from 'react'
import { Button } from '@/components/ui/button.jsx'
import { Input } from '@/components/ui/input.jsx'
import { Label } from '@/components/ui/label.jsx'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog.jsx'
import { getRecaptchaToken, recaptchaErrorMessage } from '@/lib/recaptcha.js'
import RecaptchaNotice from '@/components/RecaptchaNotice.jsx'
import { beginOwnAccountDeletion } from '@/lib/account-deletion.js'

function AccountEmailForm({ app, required = false, onSaved, onDismiss }) {
  const [email, setEmail] = useState(app.user.email || '')
  const [code, setCode] = useState('')
  const [sent, setSent] = useState(false)
  const [expiry, setExpiry] = useState(5)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  const sendCode = async () => {
    if (busy) return
    setBusy('send')
    setError('')
    setMessage('')
    try {
      const token = await getRecaptchaToken('account_email_code')
      const response = await fetch('/api/auth/account-email/send-verification-code', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim(), recaptcha_token: token }),
      })
      const result = await response.json()
      if (!response.ok) throw new Error(result.error || 'Unable to send the verification email.')
      setSent(true)
      setCode('')
      setExpiry(result.expiry_minutes || 5)
      setMessage('Verification code sent.')
    } catch (failure) {
      setError(recaptchaErrorMessage(failure, failure.message || 'Unable to send the verification email.'))
    } finally { setBusy('') }
  }

  const save = async (event) => {
    event.preventDefault()
    if (busy) return
    setBusy('save')
    setError('')
    try {
      const response = await fetch('/api/auth/account-email', {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim(), verification_code: code }),
      })
      const result = await response.json()
      if (!response.ok) throw new Error(result.error || 'Unable to verify your email.')
      app.setUser(result.user)
      app.showMessage(result.message, 'success')
      await app.handlePostAuth(result.user)
      onSaved?.()
    } catch (failure) {
      setError(failure.message || 'Unable to connect. Please try again.')
    } finally { setBusy('') }
  }

  return <form onSubmit={save} className="space-y-4">
    {app.user.role === 'user' && app.user.email_policy_enabled && <p className="text-sm text-muted-foreground">
      {app.user.allowed_email_domains?.length ? `Allowed domains: ${app.user.allowed_email_domains.join(', ')}. ` : ''}
      Your administrator can add an exception for another address or domain.
    </p>}
    <div className="space-y-2">
      <Label htmlFor="account-personal-email">Your email address</Label>
      <Input id="account-personal-email" type="email" autoComplete="email" required maxLength={320} value={email} disabled={!!busy}
        onChange={(event) => { setEmail(event.target.value); setCode(''); setSent(false); setMessage(''); setError('') }} />
      <Button type="button" variant="outline" onClick={sendCode} disabled={!!busy || !email.trim()} className="w-full">
        {busy === 'send' ? 'Sending…' : sent ? 'Resend code' : 'Send verification code'}
      </Button>
    </div>
    {sent && <div className="space-y-2">
      <Label htmlFor="account-email-code">Verification code</Label>
      <Input id="account-email-code" type="text" inputMode="numeric" autoComplete="one-time-code" required maxLength={6} value={code} disabled={!!busy}
        onChange={(event) => setCode(event.target.value.replace(/\D/g, '').slice(0, 6))} placeholder="Enter the 6-digit code" />
      <p className="text-sm text-muted-foreground">The code expires in {expiry} minutes. Check your spam folder if it has not arrived.</p>
    </div>}
    {message && <p role="status" className="text-sm">{message}</p>}
    {error && <p role="alert" className="text-sm text-red-700 dark:text-red-300">{error}</p>}
    <RecaptchaNotice />
    <div className="flex flex-col gap-2 sm:flex-row sm:justify-end">
      {onDismiss && <Button type="button" variant="outline" onClick={onDismiss}>Not now</Button>}
      {required && <Button type="button" variant="outline" onClick={app.logout} disabled={!!busy}>Log out</Button>}
      <Button type="submit" disabled={!!busy || !sent || code.length !== 6}>{busy === 'save' ? 'Verifying…' : required ? 'Verify and continue' : 'Verify and save email'}</Button>
    </div>
  </form>
}

export function AccountEmailRequired({ app }) {
  return <main id="main-content" className="mx-auto w-full max-w-lg px-5 py-12 sm:py-20">
    <p className="mb-3 text-sm text-muted-foreground">{app.user.school?.name}</p>
    <h1 className="mb-4 text-2xl font-semibold">Verify your email to continue</h1>
    <p className="mb-7 text-sm text-muted-foreground">
      {app.user.role === 'admin' ? 'Your superadmin requires you to verify your email at this login.' : 'Your school requires a verified, approved email for your account.'}
      {' '}Verify an email below, or log out if you do not want to provide one.
    </p>
    <AccountEmailForm key={app.user.id} app={app} required />
    {['user', 'admin'].includes(app.user.role) && <Button variant="link" className="mt-4 px-0" onClick={() => beginOwnAccountDeletion(app)}>Delete my account instead</Button>}
  </main>
}

export default function AccountEmailSettings({ app, open, onOpenChange, onCloseAutoFocus, reminder = false }) {
  return <Dialog open={open} onOpenChange={onOpenChange}>
    <DialogContent dismissOnOverlayClick={false} onCloseAutoFocus={onCloseAutoFocus}>
      <DialogHeader>
        <DialogTitle>{reminder ? 'Verify your account email' : 'Your account email'}</DialogTitle>
        <DialogDescription>{reminder
          ? 'Add your personal email and verify the code we send you. You can do this later from “Your account email” in the account menu.'
          : 'Add or change your personal account email by verifying a code sent to that address.'}</DialogDescription>
      </DialogHeader>
      {open && <AccountEmailForm key={app.user.id} app={app} onSaved={() => onOpenChange(false)} onDismiss={reminder ? () => onOpenChange(false) : undefined} />}
    </DialogContent>
  </Dialog>
}
