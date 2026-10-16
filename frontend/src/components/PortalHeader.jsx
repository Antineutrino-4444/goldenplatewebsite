import { Building2, MapPinned, Utensils } from 'lucide-react'
import ThemeToggle from '@/components/ThemeToggle.jsx'
import AccountMenu from '@/components/AccountMenu.jsx'
import { Button } from '@/components/ui/button.jsx'
import { NavLink } from 'react-router-dom'
import Link from '@/components/SiteLink.jsx'

export default function PortalHeader({ app, interschool = false }) {
  const school = app.user?.school
  const code = (school?.code ?? school?.slug ?? '').trim()

  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto max-w-7xl px-4 py-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0 flex-1">
            <Link to="/" aria-label="Golden Plate home" className="whitespace-nowrap text-xl font-bold tracking-tight text-amber-600 sm:text-2xl">PLATE</Link>
            <p className="sr-only mt-1 text-sm leading-relaxed text-slate-500 md:not-sr-only">
              {interschool ? 'Inter-School Control Center' : 'Prevention, Logging & Assessment of Tossed Edibles'}
            </p>
          </div>
          <nav aria-label="Portal navigation" className="flex shrink-0 items-center gap-2 sm:gap-3">
            {!interschool && <Button asChild variant="ghost" className="h-10 whitespace-nowrap px-2 text-slate-600 sm:px-3">
              <Link to="/live-counter"><Utensils className="hidden h-4 w-4 min-[420px]:block" aria-hidden="true" />
                <span className="sm:hidden">Live</span><span className="hidden sm:inline">Live counter</span>
              </Link>
            </Button>}
            {!interschool && <Button asChild variant="ghost" className="h-10 whitespace-nowrap px-2 text-slate-600 sm:px-3">
              <Link to="/map">
                <MapPinned className="hidden h-4 w-4 min-[420px]:block" aria-hidden="true" />
                <span className="sm:hidden">Map</span><span className="hidden sm:inline">School map</span>
              </Link>
            </Button>}
            <ThemeToggle />
            <AccountMenu key={app.user?.id || app.user?.username} app={app} />
          </nav>
        </div>
        {school?.name && <div className="mt-3 flex min-w-0 flex-wrap items-start gap-2 border-t border-slate-100 pt-3 text-xs text-slate-500 sm:text-sm">
          <Building2 className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span className="min-w-0 [overflow-wrap:anywhere]">{school.name}
            {code && <span className="ml-2 inline-block rounded bg-slate-100 px-1.5 py-0.5 text-xs font-medium text-slate-600 [overflow-wrap:anywhere]">Code: {code}</span>}
          </span>
        </div>}
        {!interschool && <nav aria-label="School workspace" className="mt-4 flex flex-wrap gap-2 border-t border-slate-100 pt-3 text-xs font-medium">
          {[
            ['/portal', 'Recorder'],
            ['/portal/dashboard', 'Session dashboard'],
            ...(['admin', 'superadmin'].includes(app.user?.role) ? [['/portal/admin', 'School administration']] : []),
          ].map(([to, label]) => <NavLink key={to} end to={to} className={({ isActive }) => `rounded-md px-3 py-2 ${isActive ? 'bg-emerald-50 text-emerald-800' : 'text-slate-500 hover:bg-slate-50'}`}>{label}</NavLink>)}
        </nav>}
      </div>
    </header>
  )
}
