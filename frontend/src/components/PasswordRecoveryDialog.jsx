import { useState } from 'react'
import { Button } from '@/components/ui/button.jsx'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog.jsx'
import { Input } from '@/components/ui/input.jsx'
import { Label } from '@/components/ui/label.jsx'
import CaptchaVerification from '@/components/CaptchaVerification.jsx'
import { getCaptchaToken, captchaErrorMessage } from '@/lib/captcha.js'

function RecoveryForm({ identifier, onClose }) {
  const [account, setAccount] = useState(identifier || '')
  const [confirmed, setConfirmed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const send = async (event) => {
    event.preventDefault()
    if (busy || !confirmed) return
    setBusy(true); setError('')
    try {
      const captchaToken = await getCaptchaToken('password_recovery')
      const response = await fetch('/api/auth/password-recovery/request', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ identifier: account.trim(), confirmed: true, captcha_token: captchaToken }),
      })
      const result = await response.json()
      if (!response.ok) throw new Error(result.error || 'Unable to request recovery.')
      setMessage(result.message)
    } catch (failure) { setError(captchaErrorMessage(failure, failure.message || 'Unable to connect. Try again.')) }
    finally { setBusy(false) }
  }
  if (message) return <div className="space-y-4"><p role="status" className="text-sm">{message}</p><Button onClick={onClose} className="w-full">Back to login</Button></div>
  return <form onSubmit={send} className="space-y-4">
    <p className="text-sm">A school superadmin can reset your password without sending an email. If one is available and you do not need access right away, please ask them first to help reduce email sends.</p>
    <div className="space-y-2"><Label htmlFor="recovery-account">Username or verified email</Label>
      <Input id="recovery-account" autoComplete="username" required maxLength={320} value={account} disabled={busy} onChange={(event) => setAccount(event.target.value)} />
      <p className="text-sm text-muted-foreground">Use your username if you share an email with another account. Recovery needs an email you have already verified.</p>
    </div>
    <label className="flex items-start gap-3 text-sm"><input type="checkbox" className="mt-1 h-4 w-4 shrink-0" checked={confirmed} disabled={busy} onChange={(event) => setConfirmed(event.target.checked)} required />
      <span>I want to send a password recovery email now.</span></label>
    {error && <p role="alert" className="text-sm text-red-700 dark:text-red-300">{error}</p>}
    <CaptchaVerification actions="password_recovery" />
    <div className="flex flex-col gap-2 sm:flex-row sm:justify-end"><Button type="button" variant="outline" onClick={onClose}>Ask a superadmin instead</Button>
      <Button type="submit" disabled={busy || !confirmed || !account.trim()}>{busy ? 'Sending…' : 'Send recovery email'}</Button></div>
  </form>
}

export default function PasswordRecoveryDialog({ open, onOpenChange, identifier }) {
  return <Dialog open={open} onOpenChange={onOpenChange}>
    <DialogContent dismissOnOverlayClick={false}>
      <DialogHeader><DialogTitle>Recover your password</DialogTitle><DialogDescription>Choose how to reset your password. You will still need a password to log in.</DialogDescription></DialogHeader>
      {open && <RecoveryForm identifier={identifier} onClose={() => onOpenChange(false)} />}
    </DialogContent>
  </Dialog>
}
