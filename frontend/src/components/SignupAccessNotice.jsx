import { useState } from 'react'
import SiteLink from '@/components/SiteLink.jsx'
import { Button } from '@/components/ui/button.jsx'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog.jsx'

export default function SignupAccessNotice({ app }) {
  const [open, setOpen] = useState(true)
  const [busy, setBusy] = useState(false)
  const [failed, setFailed] = useState(false)
  const guest = app.user?.role === 'guest'
  const message = guest
    ? 'Log out of guest mode to request an account or register a school.'
    : 'Log out to request another account or register a school, or return to your portal.'
  const leave = async () => {
    setBusy(true)
    setFailed(false)
    if (!await app.logout()) { setFailed(true); setBusy(false) }
  }
  const actions = <div className="flex flex-wrap gap-3"><Button onClick={leave} disabled={busy}>{busy ? 'Logging out…' : 'Log out and continue'}</Button><SiteLink to="/portal" className="gp-text-link">Return to portal</SiteLink></div>
  return <main id="main-content" className="auth-page mx-auto max-w-2xl px-6 py-14">
    <h1 className="mb-5 font-serif text-4xl">Log out before signing up.</h1><p className="mb-6">{message}</p>{actions}
    {failed && <p role="alert" className="mt-4 text-red-700">Unable to log out. Check your connection and try again.</p>}
    <Dialog open={open} onOpenChange={setOpen}><DialogContent><DialogHeader><DialogTitle>Unable to sign up while signed in</DialogTitle><DialogDescription>{message}</DialogDescription></DialogHeader>{actions}{failed && <p role="alert" className="text-red-700">Unable to log out. Check your connection and try again.</p>}</DialogContent></Dialog>
  </main>
}
