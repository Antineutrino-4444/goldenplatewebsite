import VideoHelp from '@/components/VideoHelp.jsx'
import { useEffect, useId, useState } from 'react'
import { KeyRound } from 'lucide-react'
import { Button } from '@/components/ui/button.jsx'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog.jsx'
import { Input } from '@/components/ui/input.jsx'
import { Label } from '@/components/ui/label.jsx'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs.jsx'

function PasswordForm({ reset, accounts, loading, loadError, reload, busy, setBusy }) {
  const id = useId()
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [passwordAction, setPasswordAction] = useState('custom')
  const [targetId, setTargetId] = useState('')
  const [search, setSearch] = useState('')
  const [message, setMessage] = useState(null)
  const target = accounts.find((account) => account.id === targetId)
  const resetToDefault = reset && passwordAction === 'default'
  const visibleAccounts = accounts.filter((account) => {
    const text = `${account.username} ${account.name} ${account.school?.name || ''} ${account.school?.slug || ''}`
    return account.id === targetId || text.toLowerCase().includes(search.toLowerCase())
  })

  const submit = async (event) => {
    event.preventDefault()
    setMessage(null)
    if (!resetToDefault && newPassword !== confirmation) {
      setMessage({ error: true, text: 'New passwords do not match.' })
      return
    }
    if (reset && !target) {
      setMessage({ error: true, text: 'Choose an account to reset.' })
      return
    }
    setBusy(true)
    try {
      const response = await fetch(`/api/auth/${reset ? 'reset-password' : 'change-password'}`, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          current_password: currentPassword,
          ...(resetToDefault ? { reset_to_default: true } : { new_password: newPassword }),
          ...(reset ? { user_id: targetId } : {}),
        }),
      })
      const result = await response.json()
      if (!response.ok) {
        setMessage({ error: true, text: result.error || 'Unable to update the password.' })
        return
      }
      setCurrentPassword('')
      setNewPassword('')
      setConfirmation('')
      setMessage({ error: false, text: result.message })
    } catch {
      setMessage({ error: true, text: 'Unable to connect. Please try again.' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      {reset && (
        <div className="space-y-2">
          {loading ? (
            <p role="status" className="text-sm text-gray-600">Loading accounts…</p>
          ) : loadError ? (
            <div role="alert" className="space-y-2 text-sm text-red-700">
              <p>{loadError}</p>
              <Button type="button" variant="outline" size="sm" onClick={reload}>Try again</Button>
            </div>
          ) : accounts.length === 0 ? (
            <p className="text-sm text-gray-600">No other accounts are available to reset.</p>
          ) : (
            <>
              <Label htmlFor={`${id}-search`}>Find an account</Label>
              <Input id={`${id}-search`} value={search} onChange={(event) => setSearch(event.target.value)}
                placeholder="Search by username, name or school" disabled={busy} />
              <Label htmlFor={`${id}-account`}>Account to manage</Label>
              <select id={`${id}-account`} value={targetId} required disabled={busy}
                className="h-10 w-full min-w-0 rounded-md border bg-white px-3 text-sm"
                onChange={(event) => {
                  setTargetId(event.target.value)
                  setCurrentPassword('')
                  setNewPassword('')
                  setConfirmation('')
                  setPasswordAction('custom')
                  setMessage(null)
                }}>
                <option value="">Choose an account</option>
                {visibleAccounts.map((account) => (
                  <option key={account.id} value={account.id}>
                    @{account.username} — {account.name} — {account.school?.name || account.role}
                  </option>
                ))}
              </select>
              {target && (
                <p className="text-sm text-gray-600 break-words">
                  Updating @{target.username} ({target.role}). Share the new password with this person securely.
                </p>
              )}
            </>
          )}
        </div>
      )}
      {reset && (
        <fieldset disabled={busy} className="space-y-2 rounded-md border p-3">
          <legend className="px-1 text-sm font-medium">Password action</legend>
          {[
            { value: 'custom', label: 'Set a new password' },
            { value: 'default', label: 'Reset to default: 114514' },
          ].map((action) => (
            <label key={action.value} className="flex items-center gap-2 text-sm">
              <input type="radio" name={`${id}-action`} value={action.value}
                checked={passwordAction === action.value}
                onChange={() => {
                  setPasswordAction(action.value)
                  setNewPassword('')
                  setConfirmation('')
                  setMessage(null)
                }} />
              {action.label}
            </label>
          ))}
          {resetToDefault && target && (
            <p className="text-sm text-gray-600 break-words">The password for @{target.username} will be set to 114514.</p>
          )}
        </fieldset>
      )}
      <div className="space-y-2">
        <Label htmlFor={`${id}-current`}>Your current password</Label>
        <Input id={`${id}-current`} type="password" autoComplete="current-password" required
          value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} disabled={busy} />
        {reset && <p className="text-xs text-gray-500">Enter your own password to authorize this reset.</p>}
      </div>
      {!resetToDefault && <div className="space-y-2">
        <Label htmlFor={`${id}-new`}>{reset ? 'New password for this account' : 'New password'}</Label>
        <Input id={`${id}-new`} type="password" autoComplete="new-password" required minLength={6} maxLength={256}
          value={newPassword} onChange={(event) => setNewPassword(event.target.value)} disabled={busy}
          aria-describedby={`${id}-hint`} />
        <p id={`${id}-hint`} className="text-xs text-gray-500">Use at least 6 characters.</p>
      </div>}
      {!resetToDefault && <div className="space-y-2">
        <Label htmlFor={`${id}-confirm`}>Confirm new password</Label>
        <Input id={`${id}-confirm`} type="password" autoComplete="new-password" required minLength={6} maxLength={256}
          value={confirmation} onChange={(event) => setConfirmation(event.target.value)} disabled={busy} />
      </div>}
      {message && (
        <p role={message.error ? 'alert' : 'status'}
          className={`text-sm ${message.error ? 'text-red-700' : 'text-green-700'}`}>{message.text}</p>
      )}
      <p className="text-xs text-gray-500">
        {reset ? 'This account will be signed out on its other devices.' : 'You will stay signed in here. Your other devices will need to log in again.'}
      </p>
      <Button type="submit" className="w-full" disabled={busy || (reset && (loading || Boolean(loadError) || !target))}>
        {busy ? 'Saving…' : resetToDefault ? 'Reset password to 114514' : reset ? 'Set account password' : 'Change my password'}
      </Button>
    </form>
  )
}

export default function PasswordSettings({ user, open: controlledOpen, onOpenChange, hideTrigger = false, onCloseAutoFocus }) {
  const [internalOpen, setInternalOpen] = useState(false)
  const open = controlledOpen ?? internalOpen
  const setOpen = onOpenChange || setInternalOpen
  const [mode, setMode] = useState('own')
  const [busy, setBusy] = useState(false)
  const [accounts, setAccounts] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [attempt, setAttempt] = useState(0)
  const canReset = ['superadmin', 'inter_school'].includes(user?.role)

  useEffect(() => {
    if (!open || !canReset) return
    const controller = new AbortController()
    setLoading(true)
    setLoadError('')
    setAccounts([])
    fetch('/api/auth/password-accounts', { credentials: 'same-origin', signal: controller.signal })
      .then(async (response) => {
        const result = await response.json()
        if (!response.ok) throw new Error(result.error || 'Unable to load accounts.')
        if (!controller.signal.aborted) setAccounts(result.users || [])
      })
      .catch((error) => {
        if (!controller.signal.aborted) setLoadError(error.message || 'Unable to load accounts.')
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [open, canReset, attempt])

  if (!user || user.role === 'guest') return null

  const formProps = { accounts, loading, loadError, reload: () => setAttempt((value) => value + 1), busy, setBusy }
  return (
    <Dialog open={open} onOpenChange={(value) => { if (!busy) setOpen(value) }}>
      {!hideTrigger && <DialogTrigger asChild>
        <Button variant="outline" size="sm" onClick={() => setMode('own')}>
          <KeyRound className="mr-2 h-4 w-4" />
          {canReset ? 'Passwords' : 'Change password'}
        </Button>
      </DialogTrigger>}
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg" dismissOnOverlayClick={false} onCloseAutoFocus={onCloseAutoFocus}>
        <DialogHeader>
          <DialogTitle>{canReset ? 'Manage passwords' : 'Change your password'}</DialogTitle>
          <DialogDescription>
            {canReset
              ? user.role === 'inter_school'
                ? 'Change your own password or reset an account across schools.'
                : 'Change your own password or manage passwords for users and school admins in your school.'
              : 'Confirm your current password and choose a new one.'}
          </DialogDescription>
        </DialogHeader>
        <VideoHelp videos={[22]} label="Watch: keep your account secure" />
        {canReset ? (
          <Tabs value={mode} onValueChange={(value) => { if (!busy) setMode(value) }}>
            <TabsList className="w-full">
              <TabsTrigger value="own" className="flex-1" disabled={busy}>My password</TabsTrigger>
              <TabsTrigger value="reset" className="flex-1" disabled={busy}>Other accounts</TabsTrigger>
            </TabsList>
            <TabsContent value="own"><PasswordForm {...formProps} reset={false} /></TabsContent>
            <TabsContent value="reset"><PasswordForm {...formProps} reset /></TabsContent>
          </Tabs>
        ) : <PasswordForm {...formProps} reset={false} />}
      </DialogContent>
    </Dialog>
  )
}
