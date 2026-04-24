import './App.css'
import { usePlateApp } from '@/hooks/usePlateApp.js'
import LoginView from '@/components/LoginView.jsx'
import InterschoolPortal from '@/components/InterschoolPortal.jsx'
import MainPortal from '@/components/MainPortal.jsx'
import MapPortal from '@/components/MapPortal.jsx'
import OverlayElements from '@/components/OverlayElements.jsx'
import SchoolRegistration from '@/components/SchoolRegistration.jsx'

const MAP_HOSTNAME = 'map.goldenplate.ca'

function isMapSubdomain() {
  return typeof window !== 'undefined' && window.location.hostname.toLowerCase() === MAP_HOSTNAME
}

function isMapPath() {
  if (typeof window === 'undefined') {
    return false
  }
  const path = window.location.pathname.replace(/\/+$/, '') || '/map'
  return path === '/map' || path.startsWith('/map/') || path === '/maps' || path.startsWith('/maps/')
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
      <MapPortal app={app} />
      <OverlayElements app={app} />
    </>
  )
}

function App() {
  if (isMapSubdomain() || isMapPath()) {
    return <MapApp />
  }

  return <PlateApp />
}

export default App

