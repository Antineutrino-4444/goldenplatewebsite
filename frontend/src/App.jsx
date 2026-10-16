import { Suspense, lazy, useEffect } from 'react'
import './App.css'
import { usePlateApp } from '@/hooks/usePlateApp.js'
import LoginView from '@/components/LoginView.jsx'
import InterschoolPortal from '@/components/InterschoolPortal.jsx'
import MainPortal from '@/components/MainPortal.jsx'
import OverlayElements from '@/components/OverlayElements.jsx'
import SchoolRegistration from '@/components/SchoolRegistration.jsx'
import { AlertTriangle } from 'lucide-react'

const MapPortal = lazy(() => import('@/components/SchoolMapPortal.jsx'))
const LiveCounterPage = lazy(() => import('@/components/LiveCounterPage.jsx'))

function DevelopmentModeBanner({ app }) {
  if (!app.appEnvironment?.is_development) {
    return null
  }

  return (
    <div className="border-b border-amber-300 bg-amber-100 px-4 py-2 text-amber-950">
      <div className="mx-auto flex max-w-7xl items-center justify-center gap-2 text-center text-sm font-medium">
        <AlertTriangle className="h-4 w-4 shrink-0 text-amber-700" aria-hidden="true" />
        <span>
          Development mode is active. Default development admin credentials are enabled. Set APP_ENV=production before deploying.
        </span>
      </div>
    </div>
  )
}

function AppFrame({ app, children }) {
  return (
    <>
      <DevelopmentModeBanner app={app} />
      {children}
    </>
  )
}

function isMapHost() {
  if (typeof window === 'undefined') {
    return false
  }
  const host = (window.location.hostname || '').toLowerCase()
  // Treat any host beginning with `map.` as the dedicated Ecological Map
  // subdomain (e.g. map.goldenplate.ca, map.localhost, map.staging.example).
  return host === 'map.goldenplate.ca' || host.startsWith('map.')
}

function isMapPath() {
  if (typeof window === 'undefined') {
    return false
  }
  if (isMapHost()) {
    return true
  }
  const path = window.location.pathname.replace(/\/+$/, '') || '/'
  return path === '/map' || path.startsWith('/map/')
}

function isLoginPath() {
  if (typeof window === 'undefined') {
    return false
  }
  const path = window.location.pathname.replace(/\/+$/, '') || '/'
  return path === '/login' || path.startsWith('/login/')
}

function LoginRoute({ app }) {
  // After successful login on /login, send the user to the appropriate landing
  // page based on the current host (map subdomain stays on the map; otherwise
  // the main portal). This avoids leaving them on the /login URL.
  useEffect(() => {
    if (app.isAuthenticated) {
      const target = isMapHost() ? '/' : '/'
      if (window.location.pathname !== target) {
        window.location.replace(target)
      }
    }
  }, [app.isAuthenticated])

  if (app.isAuthenticated) {
    // Brief blank while the redirect runs.
    return (
      <AppFrame app={app}>
        <div className="min-h-screen bg-gray-50" />
      </AppFrame>
    )
  }

  if (app.showSchoolRegistration) {
    return (
      <AppFrame app={app}>
        <SchoolRegistration app={app} />
        <OverlayElements app={app} />
      </AppFrame>
    )
  }

  return (
    <AppFrame app={app}>
      <LoginView app={app} />
      <OverlayElements app={app} />
    </AppFrame>
  )
}

function PlateApp() {
  const app = usePlateApp()

  if (!app.isAuthenticated) {
    if (app.showSchoolRegistration) {
      return (
        <AppFrame app={app}>
          <SchoolRegistration app={app} />
          <OverlayElements app={app} />
        </AppFrame>
      )
    }
    return (
      <AppFrame app={app}>
        <LoginView app={app} />
        <OverlayElements app={app} />
      </AppFrame>
    )
  }

  if (app.isInterschoolUser) {
    return (
      <AppFrame app={app}>
        <InterschoolPortal app={app} />
        <OverlayElements app={app} />
      </AppFrame>
    )
  }

  return (
    <AppFrame app={app}>
      <MainPortal app={app} />
      <OverlayElements app={app} />
    </AppFrame>
  )
}

function MapApp() {
  const app = usePlateApp()

  return (
    <AppFrame app={app}>
      <Suspense fallback={<div className="min-h-screen bg-slate-50" />}>
        <MapPortal app={app} />
      </Suspense>
      <OverlayElements app={app} />
    </AppFrame>
  )
}

function App() {
  if ((window.location.pathname.replace(/\/+$/, '') || '/') === '/live-counter') {
    return <Suspense fallback={<div className="min-h-screen bg-slate-50" />}><LiveCounterPage /></Suspense>
  }
  if (isLoginPath()) {
    // Dedicated /login route: always show the login screen regardless of host
    // (e.g. works on map.goldenplate.ca/login as well as goldenplate.ca/login).
    // This avoids relying on the implicit "/" → login redirect, which could
    // get swallowed by the map subdomain.
    return <LoginRouteWrapper />
  }

  if (isMapPath()) {
    return <MapApp />
  }

  return <PlateApp />
}

function LoginRouteWrapper() {
  const app = usePlateApp()
  return <LoginRoute app={app} />
}

export default App
