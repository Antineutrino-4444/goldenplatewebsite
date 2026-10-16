import { Suspense, lazy, useCallback, useEffect } from 'react'
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation, useNavigate, useParams } from 'react-router-dom'
import './App.css'
import { usePlateApp } from '@/hooks/usePlateApp.js'
import { isMapHost, safeReturnPath } from '@/lib/navigation.js'
import { AlertTriangle } from 'lucide-react'
import SchoolArrival from '@/components/SchoolArrival.jsx'
import SiteShell, { RouteContent } from '@/components/SiteShell.jsx'
import { originState } from '@/components/SiteLink.jsx'
import GuestSessionBoundary from '@/components/GuestSessionBoundary.jsx'

const LandingPage = lazy(() => import('@/components/LandingPage.jsx'))
const PodcastTranscriptPage = lazy(() => import('@/components/PodcastTranscriptPage.jsx'))
const GettingStartedPage = lazy(() => import('@/components/GettingStartedPage.jsx'))
const SignupAccessNotice = lazy(() => import('@/components/SignupAccessNotice.jsx'))
const GuestSessionPage = lazy(() => import('@/components/GuestSessionPage.jsx'))
const SchoolGuestEntry = lazy(() => import('@/components/SchoolGuestEntry.jsx'))
const LoginView = lazy(() => import('@/components/LoginView.jsx'))
const SchoolRegistration = lazy(() => import('@/components/SchoolRegistration.jsx'))
const InterschoolPortal = lazy(() => import('@/components/InterschoolPortal.jsx'))
const MainPortal = lazy(() => import('@/components/MainPortal.jsx'))
const OverlayElements = lazy(() => import('@/components/OverlayElements.jsx'))
const MapPortal = lazy(() => import('@/components/SchoolMapPortal.jsx'))
const LiveCounterPage = lazy(() => import('@/components/LiveCounterPage.jsx'))
const CommunityCounter = lazy(() => import('@/components/CommunityCounter.jsx'))

function LoadingPage() {
  return <div className="min-h-screen bg-[var(--site-paper)] flex items-center justify-center text-sm text-[var(--site-muted)]" role="status">Opening Golden Plate…</div>
}

function AppFrame({ app, children }) {
  return <>
    {app.appEnvironment?.is_development && <div className="border-b border-amber-300 bg-amber-100 px-4 py-2 text-amber-950"><div className="mx-auto flex max-w-7xl items-center justify-center gap-2 text-center text-sm font-medium"><AlertTriangle className="h-4 w-4 shrink-0 text-amber-700" aria-hidden="true" /><span>Development mode is active. Default development admin credentials are enabled. Set APP_ENV=production before deploying.</span></div></div>}
    {children}
  </>
}

function Workspace() {
  const app = usePlateApp()
  const location = useLocation()
  const navigate = useNavigate()
  const { schoolId } = useParams()
  const path = location.pathname.replace(/\/+$/, '')
  const registration = path === '/register'
  const signup = path === '/signup'
  const guestEntry = path.startsWith('/guest/schools/')
  const authentication = path === '/login' || registration || signup || guestEntry
  const map = isMapHost(window.location.hostname)
  const fallback = map ? '/map' : app.isInterschoolUser ? '/interschool' : '/portal'
  const target = safeReturnPath(new URLSearchParams(location.search).get('next'), fallback)
  const setLoginFlight = app.setLoginFlight
  const skipFlight = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  const showFlight = authentication && !registration && app.isAuthenticated && app.loginFlight && !skipFlight && !app.isInterschoolUser && app.user?.role !== 'guest' && target.split(/[?#]/)[0] === '/portal'
  const finishFlight = useCallback(() => {
    navigate(target, { replace: true, state: { schoolArrival: true } })
  }, [navigate, target])
  useEffect(() => {
    if (!authentication && app.loginFlight) setLoginFlight(false)
  }, [authentication, app.loginFlight, setLoginFlight])
  useEffect(() => {
    if (!location.state?.schoolArrival || authentication || !app.authReady || !app.isAuthenticated) return
    const frame = requestAnimationFrame(() => {
      const heading = document.getElementById('record-entry-title')
      if (heading) { heading.tabIndex = -1; heading.focus({ preventScroll: true }) }
    })
    return () => cancelAnimationFrame(frame)
  }, [location.key, location.state?.schoolArrival, authentication, app.authReady, app.isAuthenticated])

  useEffect(() => {
    document.title = `${guestEntry ? 'School guest access' : registration ? 'Register your school' : authentication ? 'School login' : app.isInterschoolUser ? 'Inter-school administration' : path.endsWith('/dashboard') ? 'Session dashboard' : path.endsWith('/admin') ? 'School administration' : 'School portal'} · Golden Plate`
  }, [guestEntry, registration, authentication, path, app.isInterschoolUser])
  useEffect(() => { app.setShowSignupDialog(signup) }, [signup, app.setShowSignupDialog])
  // Dedicated URLs keep the existing registration workflow and success notices.
  const routeApp = {
    ...app,
    signupPage: signup,
    pageSection: path === '/portal/dashboard' ? 'dashboard' : path === '/portal/admin' ? 'admin' : 'recorder',
    signup: async () => { if (await app.signup()) navigate('/login', { replace: true }) },
    registerSchool: async () => { if (await app.registerSchool()) navigate('/login', { replace: true }) },
    showSchoolRegistration: registration,
    setShowSchoolRegistration: (open) => navigate(open ? '/register' : '/login', { state: originState(location) }),
    setShowSignupDialog: (open) => navigate(open ? '/signup' : '/login', { state: originState(location) }),
    showDashboard: path === '/portal/dashboard',
    setShowDashboard: (open) => navigate(open ? '/portal/dashboard' : '/portal'),
    showAdminPanel: path === '/portal/admin' && ['admin', 'superadmin'].includes(app.user?.role),
    setShowAdminPanel: (open) => navigate(open ? '/portal/admin' : '/portal'),
  }
  useEffect(() => {
    if (app.isAuthenticated && path === '/portal/admin' && ['admin', 'superadmin'].includes(app.user?.role)) app.loadAdminData()
  }, [app.isAuthenticated, app.user?.role, path])

  if (!app.authReady) return <LoadingPage />
  if (guestEntry) return <AppFrame app={app}><Suspense fallback={<LoadingPage />}><SchoolGuestEntry key={schoolId} schoolId={schoolId} guestLogin={app.guestLogin} /><OverlayElements app={app} /></Suspense></AppFrame>
  if ((signup || registration) && app.isAuthenticated) return <AppFrame app={app}><SignupAccessNotice app={app} /><Suspense fallback={null}><OverlayElements app={app} /></Suspense></AppFrame>
  if (authentication && app.isAuthenticated && !registration && !signup) {
    if (!showFlight) return <Navigate to={target} replace />
  }
  if (!authentication && !app.isAuthenticated) return <Navigate to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`} replace />
  if (!authentication && !['/portal', '/portal/dashboard', '/portal/admin', '/interschool'].includes(path)) return <NotFound />
  if (!authentication && path === '/interschool' && !app.isInterschoolUser) return <Navigate to="/portal" replace />
  if (!authentication && app.isInterschoolUser && path !== '/interschool') return <Navigate to="/interschool" replace />
  if (!authentication && path === '/portal/admin' && !['admin', 'superadmin'].includes(app.user?.role)) return <Navigate to="/portal" replace />

  return <><div className={showFlight ? 'arrival-portal' : undefined} inert={showFlight || undefined} aria-hidden={showFlight || undefined}><AppFrame app={app}><Suspense fallback={<LoadingPage />}>
    {authentication && !showFlight ? <div className="auth-page">{!registration && <div className="auth-intro"><h1>{signup ? 'Join your school community.' : 'Welcome back to your school.'}</h1><p>{signup ? 'Request an account or use an invite from your administrator.' : 'Small actions add up. Pick up where your community left off.'}</p></div>}<main id="main-content">{registration ? <SchoolRegistration app={routeApp} /> : <LoginView app={routeApp} />}</main></div> : app.isInterschoolUser ? <InterschoolPortal app={routeApp} /> : <MainPortal app={routeApp} />}
    {!showFlight && <OverlayElements app={routeApp} />}
  </Suspense></AppFrame></div>{showFlight && <SchoolArrival user={app.user} onComplete={finishFlight} />}</>
}

function MapApp() {
  const app = usePlateApp()
  return <AppFrame app={app}><Suspense fallback={<LoadingPage />}><MapPortal app={app} /><OverlayElements app={app} /></Suspense></AppFrame>
}

function NotFound() {
  return <div className="auth-page"><main id="main-content" className="mx-auto max-w-xl px-6 py-24 text-center"><p className="text-sm">404 · Page not found</p><h1 className="my-5 font-serif text-4xl">Let’s get you back to the table.</h1><p className="mb-7 text-sm">This page may have moved. Explore the initiative or return to your school.</p><div className="flex justify-center gap-4"><Link className="gp-button" to="/">Home</Link><Link className="gp-button" to="/portal">School portal</Link></div></main></div>
}

function SiteRoutes() {
  const mapHost = isMapHost(window.location.hostname)
  return <Suspense fallback={<LoadingPage />}><RouteContent><Routes>
    <Route path="/" element={mapHost ? <MapApp /> : <LandingPage />} />
    <Route path="/about" element={<LandingPage page="about" />} />
    <Route path="/how-it-works" element={<LandingPage page="how" />} />
    <Route path="/getting-started" element={<GettingStartedPage />} />
    <Route path="/stories" element={<LandingPage page="stories" />} />
    <Route path="/stories/transcript" element={<PodcastTranscriptPage />} />
    <Route path="/guest/sessions/:sessionId" element={<GuestSessionPage />} />
    <Route path="/map/*" element={<MapApp />} />
    <Route path="/live-counter" element={<LiveCounterPage />} />
    <Route path="/live-counter/community" element={<div className="golden-public"><main id="main-content" className="gp-container"><CommunityCounter /></main></div>} />
    <Route element={<Workspace />}>
      <Route path="/login" element={<></>} />
      <Route path="/register" element={<></>} />
      <Route path="/signup" element={<></>} />
      <Route path="/guest/schools/:schoolId" element={<></>} />
      <Route path="/portal/*" element={<></>} />
      <Route path="/interschool" element={<></>} />
    </Route>
    <Route path="*" element={<NotFound />} />
  </Routes></RouteContent></Suspense>
}

export default function App() {
  return <BrowserRouter><GuestSessionBoundary><SiteShell><SiteRoutes /></SiteShell></GuestSessionBoundary></BrowserRouter>
}
