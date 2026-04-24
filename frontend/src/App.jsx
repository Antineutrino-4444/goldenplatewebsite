import { Suspense, lazy } from 'react'
import './App.css'
import { usePlateApp } from '@/hooks/usePlateApp.js'
import LoginView from '@/components/LoginView.jsx'
import InterschoolPortal from '@/components/InterschoolPortal.jsx'
import MainPortal from '@/components/MainPortal.jsx'
import OverlayElements from '@/components/OverlayElements.jsx'
import SchoolRegistration from '@/components/SchoolRegistration.jsx'

const MapPortal = lazy(() => import('@/components/MapPortal.jsx'))

function isMapPath() {
  if (typeof window === 'undefined') {
    return false
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

  return (
    <>
      <Suspense fallback={<div className="min-h-screen bg-slate-50" />}>
        <MapPortal app={app} />
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

