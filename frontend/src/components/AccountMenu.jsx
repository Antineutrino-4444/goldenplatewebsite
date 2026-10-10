import { useRef, useState } from 'react'
import { ChevronDown, Github, KeyRound, LogOut, Mail, UserRound } from 'lucide-react'
import { Button } from '@/components/ui/button.jsx'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu.jsx'
import PasswordSettings from '@/components/PasswordSettings.jsx'
import SchoolContactSettings from '@/components/SchoolContactSettings.jsx'

export default function AccountMenu({ app }) {
  const { user, logout } = app
  const [passwordOpen, setPasswordOpen] = useState(false)
  const [contactOpen, setContactOpen] = useState(user?.role === 'superadmin' && !user.school_contact_email)
  const trigger = useRef(null)
  const canReset = ['superadmin', 'inter_school'].includes(user?.role)
  const restoreFocus = (event) => {
    event.preventDefault()
    trigger.current?.focus()
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
          if (passwordOpen || contactOpen) event.preventDefault()
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
          <DropdownMenuItem asChild>
            <a href="https://github.com/Antineutrino-4444/goldenplatewebsite" target="_blank" rel="noopener noreferrer"><Github />GitHub repository</a>
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onSelect={logout} variant="destructive"><LogOut />Log out</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      {/* Keep dialogs mounted outside the menu so closing the menu neither
          closes them nor suppresses the automatic missing-email reminder. */}
      <PasswordSettings user={user} open={passwordOpen} onOpenChange={setPasswordOpen} hideTrigger onCloseAutoFocus={restoreFocus} />
      {user.role === 'superadmin' && <SchoolContactSettings app={app} open={contactOpen} onOpenChange={setContactOpen} hideTrigger onCloseAutoFocus={restoreFocus} />}
    </>
  )
}
