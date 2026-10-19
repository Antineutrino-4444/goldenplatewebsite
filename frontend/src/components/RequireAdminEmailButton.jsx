import { useState } from 'react'
import { Button } from '@/components/ui/button.jsx'

export default function RequireAdminEmailButton({ app, account }) {
  const [busy, setBusy] = useState(false)
  if (app.user.role !== 'superadmin' || account.role !== 'admin') return null
  const requireEmail = async () => {
    if (busy) return
    setBusy(true)
    try {
      const response = await fetch(`/api/superadmin/users/${encodeURIComponent(account.id)}/require-email`, { method: 'POST' })
      const result = await response.json()
      if (!response.ok) throw new Error(result.error || 'Unable to require email verification.')
      app.showMessage(result.message, 'success')
      await Promise.all([app.loadAllUsers(), app.loadAdminData()])
    } catch (failure) {
      app.showMessage(failure.message || 'Unable to connect. Please try again.', 'error')
    } finally { setBusy(false) }
  }
  return <Button size="sm" variant="outline" onClick={requireEmail} disabled={busy || account.email_verification_requested}>
    {busy ? 'Saving…' : account.email_verification_requested ? 'Email required at next login' : 'Require email verification'}
  </Button>
}
