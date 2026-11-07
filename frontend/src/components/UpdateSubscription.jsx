import { useEffect, useState } from 'react'
import { Mail } from 'lucide-react'
import CaptchaVerification from '@/components/CaptchaVerification.jsx'
import { captchaErrorMessage, getCaptchaToken } from '@/lib/captcha.js'
import './UpdateSubscription.css'

export default function UpdateSubscription() {
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [sent, setSent] = useState(false)
  const [busy, setBusy] = useState(false)
  const [cooldown, setCooldown] = useState(0)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [success, setSuccess] = useState(false)

  useEffect(() => {
    if (!cooldown) return
    const timer = setTimeout(() => setCooldown(cooldown - 1), 1000)
    return () => clearTimeout(timer)
  }, [cooldown])

  const sendCode = async () => {
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const captchaToken = await getCaptchaToken('website_updates_code')
      const response = await fetch('/api/updates/send-verification-code', {
        method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, captcha_token: captchaToken }),
      })
      const data = await response.json()
      if (response.status === 429) setCooldown(60)
      if (!response.ok) throw new Error(data.error || 'Unable to send a code. Please try again.')
      setSent(true)
      setCode('')
      setCooldown(60)
      setNotice(`${data.message} The code expires in ${data.expiry_minutes} minutes.`)
    } catch (err) {
      setError(captchaErrorMessage(err, err.message || 'Unable to send a code. Please try again.'))
    } finally { setBusy(false) }
  }

  const submit = async (event) => {
    event.preventDefault()
    if (!sent) { await sendCode(); return }
    setBusy(true)
    setError('')
    try {
      const response = await fetch('/api/updates/subscribe', {
        method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, verification_code: code }),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.error || 'Unable to subscribe. Please try again.')
      setSuccess(true)
      setNotice([data.message, data.warning].filter(Boolean).join(' '))
    } catch (err) {
      setError(err.message || 'Unable to subscribe. Please try again.')
    } finally { setBusy(false) }
  }

  return <section id="website-updates" className="gp-update-subscription" aria-labelledby="website-updates-title">
    <div className="gp-update-intro"><Mail size={22} aria-hidden="true" /><div>
      <h2 id="website-updates-title">Get website updates.</h2>
      <p>New releases, straight to your inbox. No account needed. Unsubscribe anytime.</p>
    </div></div>
    {success ? <p className="gp-update-success" role="status">{notice}</p> : <form onSubmit={submit} aria-busy={busy}>
      <div className="gp-update-fields">
        <label htmlFor="website-updates-email">Email address
          <input id="website-updates-email" type="email" autoComplete="email" required maxLength={320}
            value={email} readOnly={sent} disabled={busy} onChange={(event) => setEmail(event.target.value)} />
        </label>
        {sent && <label htmlFor="website-updates-code">Verification code
          <input id="website-updates-code" type="text" inputMode="numeric" autoComplete="one-time-code"
            required pattern="[0-9]{6}" maxLength={6} value={code} disabled={busy} autoFocus
            onChange={(event) => setCode(event.target.value.replace(/[^0-9]/g, ''))} />
        </label>}
        <button className="gp-button" type="submit" disabled={busy || (!sent && cooldown > 0)}>
          {busy ? 'Please wait…' : sent ? 'Verify & subscribe' : 'Send verification code'}
        </button>
      </div>
      <CaptchaVerification actions="website_updates_code" />
      {sent && <div className="gp-update-actions">
        <button className="gp-text-link" type="button" disabled={busy || cooldown > 0} onClick={sendCode}>
          {cooldown ? `Resend code in ${cooldown}s` : 'Resend code'}
        </button>
        <button className="gp-text-link" type="button" disabled={busy} onClick={() => {
          setSent(false); setCode(''); setError(''); setNotice('')
        }}>Change email</button>
      </div>}
      {notice && <p className="gp-update-notice" role="status">{notice}</p>}
      {error && <p className="gp-update-error" role="alert">{error}</p>}
    </form>}
  </section>
}
