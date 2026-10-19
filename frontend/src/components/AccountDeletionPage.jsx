import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button.jsx'
import { Input } from '@/components/ui/input.jsx'
import { Label } from '@/components/ui/label.jsx'

export default function AccountDeletionPage() {
  const [token] = useState(() => new URLSearchParams(window.location.hash.slice(1)).get('token') || '')
  const [account, setAccount] = useState(null)
  const [step, setStep] = useState('loading')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [nonce, setNonce] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    document.title = 'Account deletion · Golden Plate'
    let active = true
    fetch('/api/account-deletion/inspect', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token }),
    }).then(async (response) => {
      const data = await response.json()
      if (!response.ok) throw new Error(data.error || 'Unable to open the deletion link.')
      if (!active) return
      setAccount(data)
      setUsername(data.confirmation_role === 'owner' ? data.username || '' : '')
      setStep(data.deleted ? 'deleted' : 'signin')
    }).catch((failure) => { if (active) { setError(failure.message); setStep('error') } })
    return () => { active = false }
  }, [token])

  const next = async (action) => {
    if (busy) return
    setBusy(true)
    setError('')
    try {
      const response = await fetch(`/api/account-deletion/${action}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, nonce, ...(action === 'authorize' ? { username, password } : {}) }),
      })
      const data = await response.json()
      if (!response.ok) {
        if (response.status === 403 && action !== 'authorize') { setStep('signin'); setNonce('') }
        if (response.status === 410) setStep('error')
        throw new Error(data.error || 'Unable to confirm deletion.')
      }
      setPassword('')
      if (data.deleted) setStep('deleted')
      else { setNonce(data.nonce); setStep(action === 'authorize' ? 'first' : 'final') }
    } catch (failure) { setError(failure.message || 'Unable to connect. Please try again.') }
    finally { setBusy(false) }
  }

  return <main id="main-content" className="mx-auto w-full max-w-lg px-5 py-12 sm:py-20">
    <h1 className="mb-4 text-2xl font-semibold">{step === 'deleted' ? 'Account deleted' : 'Delete account'}</h1>
    {step === 'loading' && <p role="status">Checking the account…</p>}
    {account && !account.deleted && step !== 'deleted' && <p className="mb-6 text-sm [overflow-wrap:anywhere]">{account.name} · @{account.username}<br />{account.school}</p>}
    {step === 'signin' && <form onSubmit={(event) => { event.preventDefault(); next('authorize') }} className="space-y-4">
      <p className="text-sm">{account.confirmation_role === 'owner' ? 'The account owner must sign in to confirm this deletion. A disabled account can sign in here only to delete itself.' : 'A school superadmin must enter their own username and password to authorize this deletion.'} This sign-in does not open the school portal.</p>
      <div className="space-y-2"><Label htmlFor="deletion-username">Username</Label><Input id="deletion-username" autoComplete="username" required value={username} onChange={(event) => setUsername(event.target.value)} disabled={busy} /></div>
      <div className="space-y-2"><Label htmlFor="deletion-password">Password</Label><Input id="deletion-password" type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} disabled={busy} /></div>
      <Button type="submit" disabled={busy}>{busy ? 'Checking…' : 'Sign in to confirm deletion'}</Button>
    </form>}
    {step === 'first' && <div className="space-y-4">
      <h2 className="text-lg font-semibold">Confirmation 1 of 2</h2>
      <p className="text-sm">Deleting this account removes its login and account details. School plate records and sessions remain. The deleted account cannot be recovered.</p>
      <Button variant="destructive" onClick={() => next('prepare')} disabled={busy}>Continue to final confirmation</Button>
    </div>}
    {step === 'final' && <div className="space-y-4">
      <h2 className="text-lg font-semibold">Confirmation 2 of 2</h2>
      <p className="text-sm">Permanently delete @{account.username}? This is the final step and cannot be undone.</p>
      <Button variant="destructive" onClick={() => next('confirm')} disabled={busy}>{busy ? 'Deleting…' : 'Permanently delete this account'}</Button>
    </div>}
    {step === 'deleted' && <p role="status" className="text-sm">This account has been permanently deleted. School records and sessions are preserved.</p>}
    {error && <p role="alert" className="mt-4 text-sm text-red-700 dark:text-red-300">{error}</p>}
    <div className="mt-6"><Link to={step === 'deleted' ? '/login' : '/portal'} className="text-sm underline">{step === 'deleted' ? 'Return to login' : 'Cancel and leave this page'}</Link></div>
  </main>
}
