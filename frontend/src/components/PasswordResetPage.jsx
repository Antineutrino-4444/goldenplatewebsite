import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button.jsx'
import { Input } from '@/components/ui/input.jsx'
import { Label } from '@/components/ui/label.jsx'

export default function PasswordResetPage() {
  const [token] = useState(() => new URLSearchParams(window.location.hash.slice(1)).get('token') || '')
  const [stage, setStage] = useState('loading')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    document.title = 'Reset password · Golden Plate'
    const controller = new AbortController()
    fetch('/api/auth/password-recovery/inspect', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token }), signal: controller.signal })
      .then(async (response) => {
        const result = await response.json()
        if (!response.ok) throw new Error(result.error || 'Unable to check this link.')
        if (!controller.signal.aborted) setStage('ready')
      }).catch((failure) => { if (!controller.signal.aborted) { setError(failure.message); setStage('error') } })
    return () => controller.abort()
  }, [token])
  const save = async (event) => {
    event.preventDefault()
    if (busy) return
    if (password !== confirmation) { setError('New passwords do not match.'); return }
    setBusy(true); setError('')
    try {
      const response = await fetch('/api/auth/password-recovery/reset', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token, new_password: password }) })
      const result = await response.json()
      if (!response.ok) throw new Error(result.error || 'Unable to reset your password.')
      setPassword(''); setConfirmation(''); setStage('done')
      window.history.replaceState(null, '', window.location.pathname)
    } catch (failure) { setError(failure.message || 'Unable to connect. Try again.') }
    finally { setBusy(false) }
  }
  return <main id="main-content" className="mx-auto w-full max-w-lg px-5 py-12 sm:py-20">
    <h1 className="mb-4 text-2xl font-semibold">{stage === 'done' ? 'Password changed' : 'Choose a new password'}</h1>
    {stage === 'loading' && <p role="status">Checking your reset link…</p>}
    {stage === 'done' && <p role="status" className="mb-6">Sign in with your username or verified email and your new password.</p>}
    {stage === 'ready' && <form onSubmit={save} className="mb-6 space-y-4">
      <p className="text-sm">This changes your password and signs out your other devices. It does not sign you in.</p>
      <div className="space-y-2"><Label htmlFor="reset-password">New password</Label><Input id="reset-password" type="password" autoComplete="new-password" required minLength={6} maxLength={256} value={password} disabled={busy} onChange={(event) => setPassword(event.target.value)} /></div>
      <div className="space-y-2"><Label htmlFor="reset-password-confirm">Confirm new password</Label><Input id="reset-password-confirm" type="password" autoComplete="new-password" required minLength={6} maxLength={256} value={confirmation} disabled={busy} onChange={(event) => setConfirmation(event.target.value)} /></div>
      <Button type="submit" disabled={busy}>{busy ? 'Saving…' : 'Save new password'}</Button>
    </form>}
    {error && <p role="alert" className="mb-6 text-sm text-red-700 dark:text-red-300">{error}</p>}
    {stage !== 'loading' && <Link to="/login" className="gp-text-link">Back to login</Link>}
  </main>
}
