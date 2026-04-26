import { Suspense, lazy } from 'react'
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
  if (isMapPath()) {
    return <MapApp />
  }

  return <PlateApp />
}

export default App

