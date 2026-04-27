import { Suspense, lazy, useEffect } from 'react'
import './App.css'
import { usePlateApp } from '@/hooks/usePlateApp.js'
import LoginView from '@/components/LoginView.jsx'
import InterschoolPortal from '@/components/InterschoolPortal.jsx'
import MainPortal from '@/components/MainPortal.jsx'
import OverlayElements from '@/components/OverlayElements.jsx'
import SchoolRegistration from '@/components/SchoolRegistration.jsx'

const MapPortal = lazy(() => import('@/components/MapPortal.jsx'))

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
    return <div className="min-h-screen bg-gray-50" />
  }

  if (app.showSchoolRegistration) {
    return (
      <>
        <SchoolRegistration app={app} />
        <OverlayElements app={app} />
      </>
    )
  }

  return (
    <>
      <LoginView app={app} />
      <OverlayElements app={app} />
    </>
  )
}

function PlateApp() {
  const app = usePlateApp()

  if (!app.isAuthenticated) {
    if (app.showSchoolRegistration) {
      return (
        <>
          <SchoolRegistration app={app} />
          <OverlayElements app={app} />
        </>
      )
    }
    return (
      <>
        <LoginView app={app} />
        <OverlayElements app={app} />
      </>
    )
  }

  if (app.isInterschoolUser) {
    return (
      <>
        <InterschoolPortal app={app} />
        <OverlayElements app={app} />
      </>
    )
  }

  return (
    <>
      <MainPortal app={app} />
      <OverlayElements app={app} />
    </>
  )
}

function MapApp() {
  const app = usePlateApp()

  return (
    <>
      <Suspense fallback={<div className="min-h-screen bg-slate-50" />}>
        {app.isAuthenticated && app.isInterschoolUser ? (
          <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
            <div className="max-w-md rounded-md border bg-white p-6 text-center shadow-sm">
              <h1 className="text-xl font-bold text-slate-950">Ecological Map unavailable</h1>
              <p className="mt-2 text-sm text-slate-600">
                Inter-school admin accounts do not have access to the Ecological Map.
              </p>
              <a
                href="/"
                className="mt-4 inline-block rounded-md bg-teal-700 px-4 py-2 text-sm font-medium text-white hover:bg-teal-800"
              >
                Go to Inter-school Portal
              </a>
            </div>
          </div>
        ) : (
          <MapPortal app={app} />
        )}
      </Suspense>
      <OverlayElements app={app} />
    </>
  )
}

function App() {
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

