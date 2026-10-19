import { useRef, useState } from 'react'
import { ChevronDown, Github, KeyRound, LogOut, Mail, MapPinned, UserRound } from 'lucide-react'
import { Button } from '@/components/ui/button.jsx'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu.jsx'
import PasswordSettings from '@/components/PasswordSettings.jsx'
import SchoolContactSettings from '@/components/SchoolContactSettings.jsx'
import SchoolLocationDialog from '@/components/SchoolLocationDialog.jsx'
import AccountEmailSettings from '@/components/AccountEmailSettings.jsx'
import SchoolEmailPolicySettings from '@/components/SchoolEmailPolicySettings.jsx'
import { beginOwnAccountDeletion } from '@/lib/account-deletion.js'

function emailReminderKey(user) {
  return `gp:account-email-reminder:${user?.id}:${user?.last_login_at || 'session'}`
}

function needsEmailReminder(user) {
  if (user?.role !== 'superadmin' || (user.email && user.email_verified)) return false
  try { return sessionStorage.getItem(emailReminderKey(user)) !== 'dismissed' }
  catch { return true }
}

export default function AccountMenu({ app, onSchoolLocationSaved }) {
  const { user, logout } = app
  const [passwordOpen, setPasswordOpen] = useState(false)
  const [locationOpen, setLocationOpen] = useState(false)
  const [emailReminderPending, setEmailReminderPending] = useState(() => needsEmailReminder(user))
  const [emailOpen, setEmailOpen] = useState(() => needsEmailReminder(user) && !!user.school_contact_email)
  const [emailPolicyOpen, setEmailPolicyOpen] = useState(false)
  const [contactOpen, setContactOpen] = useState(user?.role === 'superadmin' && !user.school_contact_email)
  const trigger = useRef(null)
  const canReset = ['superadmin', 'inter_school'].includes(user?.role)
  const restoreFocus = (event) => {
    event.preventDefault()
    trigger.current?.focus()
  }
  const changeEmailOpen = (next) => {
    setEmailOpen(next)
    if (!next && emailReminderPending) {
      setEmailReminderPending(false)
      try { sessionStorage.setItem(emailReminderKey(user), 'dismissed') } catch { /* Dismissal still lasts until unmount. */ }
    }
  }
  const changeContactOpen = (next) => {
    setContactOpen(next)
    if (!next && emailReminderPending) setEmailOpen(true)
  }

  if (!user) return null

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button ref={trigger} variant="outline" className="h-10 gap-2 whitespace-nowrap px-2 sm:px-3" aria-label="Account menu">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-amber-50 text-amber-700">
              <UserRound className="h-4 w-4" aria-hidden="true" />
            </span>
            <span className="hidden max-w-36 truncate sm:block">{user.name || user.username}</span>
            <ChevronDown className="h-3.5 w-3.5" aria-hidden="true" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-64 max-w-[calc(100vw-2rem)]" onCloseAutoFocus={(event) => {
          if (passwordOpen || contactOpen || locationOpen || emailOpen || emailPolicyOpen) event.preventDefault()
        }}>
          <DropdownMenuLabel className="min-w-0 space-y-1 [overflow-wrap:anywhere]">
            <div className="font-semibold">{user.name}</div>
            <div className="text-xs font-normal text-slate-500">@{user.username} · {({ superadmin: 'Superadmin', inter_school: 'Inter-school admin', admin: 'Admin', user: 'User', guest: 'Guest' })[user.role] || user.role}</div>
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          {user.role !== 'guest' && (
            <DropdownMenuItem onSelect={() => setPasswordOpen(true)}>
              <KeyRound />{canReset ? 'Manage passwords' : 'Change password'}
            </DropdownMenuItem>
          )}
          {user.role === 'superadmin' && (
            <DropdownMenuItem onSelect={() => setContactOpen(true)}><Mail />School contact email</DropdownMenuItem>
          )}
          {['user', 'admin', 'superadmin', 'inter_school'].includes(user.role) && (
            <DropdownMenuItem onSelect={() => setLocationOpen(true)}><MapPinned />{user.role === 'inter_school' ? 'School locations' : 'School location'}</DropdownMenuItem>
          )}
          {user.role !== 'guest' && <DropdownMenuItem onSelect={() => setEmailOpen(true)}><Mail />Your account email</DropdownMenuItem>}
          {['admin', 'superadmin'].includes(user.role) && <DropdownMenuItem onSelect={() => setEmailPolicyOpen(true)}><Mail />School email rules</DropdownMenuItem>}
          <DropdownMenuItem asChild>
            <a href="https://github.com/Antineutrino-4444/goldenplatewebsite" target="_blank" rel="noopener noreferrer"><Github />GitHub repository</a>
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          {['user', 'admin'].includes(user.role) && <DropdownMenuItem onSelect={() => beginOwnAccountDeletion(app)} variant="destructive">Delete my account</DropdownMenuItem>}
          <DropdownMenuItem onSelect={logout} variant="destructive"><LogOut />Log out</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      {/* Keep dialogs mounted outside the menu so closing the menu neither
          closes them nor suppresses the automatic missing-email reminder. */}
      <PasswordSettings user={user} open={passwordOpen} onOpenChange={setPasswordOpen} hideTrigger onCloseAutoFocus={restoreFocus} />
      {user.role !== 'guest' && <AccountEmailSettings app={app} open={emailOpen} onOpenChange={changeEmailOpen} reminder={emailReminderPending} onCloseAutoFocus={restoreFocus} />}
      {['admin', 'superadmin'].includes(user.role) && <SchoolEmailPolicySettings app={app} open={emailPolicyOpen} onOpenChange={setEmailPolicyOpen} onCloseAutoFocus={restoreFocus} />}
      {user.role === 'superadmin' && <SchoolContactSettings app={app} open={contactOpen} onOpenChange={changeContactOpen} hideTrigger onCloseAutoFocus={(event) => {
        if (emailReminderPending) event.preventDefault()
        else restoreFocus(event)
      }} />}
      <SchoolLocationDialog app={app} open={locationOpen} onOpenChange={setLocationOpen} hideTrigger
        autoPrompt allowAutomaticPrompt={!contactOpen && !passwordOpen && !emailOpen && !emailPolicyOpen}
        onSaved={onSchoolLocationSaved} onCloseAutoFocus={restoreFocus} />
    </>
  )
}
