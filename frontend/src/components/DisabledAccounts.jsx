import { useCallback, useEffect, useState } from 'react'
import { Button } from '@/components/ui/button.jsx'

export default function DisabledAccounts({ app }) {
  const [accounts, setAccounts] = useState([])
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const load = useCallback(async () => {
    try {
      const response = await fetch('/api/admin/disabled-accounts')
      const data = await response.json()
      if (!response.ok) throw new Error(data.error || 'Unable to load disabled accounts.')
      setAccounts(data.accounts)
      setError('')
    } catch (failure) { setError(failure.message) }
    finally { setLoading(false) }
  }, [])
  useEffect(() => { load() }, [load, app.user.school_id, app.adminUsers])

  const action = async (account, kind) => {
    if (busy) return
    setBusy(account.id)
    setError('')
    try {
      const response = await fetch(`/api/admin/disabled-accounts/${encodeURIComponent(account.id)}/${kind}`, { method: 'POST' })
      const data = await response.json()
      if (!response.ok) throw new Error(data.error || 'Unable to update the account.')
      if (kind === 'deletion-link') {
        window.location.assign(`/account-deletion#token=${encodeURIComponent(data.token)}`)
      } else {
        app.showMessage(data.message, 'success')
        await Promise.all([load(), app.loadAllUsers(), app.loadAdminData()])
      }
    } catch (failure) { setError(failure.message || 'Unable to connect. Please try again.') }
    finally { setBusy('') }
  }

  return <section aria-label="Disabled account list">
    <div className="mb-3 flex justify-end">
      <Button variant="outline" size="sm" onClick={load} disabled={loading || !!busy}>Refresh</Button>
    </div>
    {loading && <p role="status" className="text-sm">Loading disabled accounts…</p>}
    {error && <p role="alert" className="mb-3 text-sm text-red-700 dark:text-red-300">{error}</p>}
    {!loading && accounts.length === 0 && <p className="rounded border p-4 text-sm text-muted-foreground">No disabled accounts.</p>}
    <div className="space-y-3">
      {accounts.map((account) => <div key={account.id} className="flex min-w-0 flex-col gap-3 rounded border p-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0 text-sm [overflow-wrap:anywhere]">
          <p className="font-medium">{account.name}</p>
          <p className="text-muted-foreground">@{account.username} · {account.role} · {account.reason}</p>
          {account.delete_at ? <p>{account.automatic_deletion ? 'Deletes' : 'Deletion review'}: {new Date(account.delete_at).toLocaleString(undefined, { timeZoneName: 'short' })}</p>
            : <p>No automatic deletion scheduled.</p>}
          {account.notification_failures > 0 && <p role="status" className="text-red-700 dark:text-red-300">Email delivery failed; an automatic retry is queued.</p>}
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={() => action(account, 'restore')} disabled={!!busy}>{busy === account.id ? 'Working…' : 'Recover account'}</Button>
          {app.user.role === 'superadmin' && <Button variant="destructive" size="sm" onClick={() => action(account, 'deletion-link')} disabled={!!busy}>Review deletion</Button>}
        </div>
      </div>)}
    </div>
  </section>
}
