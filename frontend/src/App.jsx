import { useEffect } from 'react'
import './App.css'
import { usePlateApp } from '@/hooks/usePlateApp.js'
import LoginView from '@/components/LoginView.jsx'
import InterschoolPortal from '@/components/InterschoolPortal.jsx'
import MainPortal from '@/components/MainPortal.jsx'
import OverlayElements from '@/components/OverlayElements.jsx'
import SchoolRegistration from '@/components/SchoolRegistration.jsx'

const MAP_HOSTNAME = 'map.goldenplate.ca'

function isMapSubdomain() {
  return typeof window !== 'undefined' && window.location.hostname.toLowerCase() === MAP_HOSTNAME
}

function isMapPath() {
  return typeof window !== 'undefined' && window.location.pathname.replace(/\/+$/, '') === '/map'
}

function MapPlaceholder() {
  useEffect(() => {
    const originalTitle = document.title
    document.title = 'Golden Plate Map'

    return () => {
      document.title = originalTitle
    }
  }, [])

  return (
    <main className="map-placeholder-page">
      <section className="map-placeholder-card" aria-labelledby="map-placeholder-title">
        <div className="map-placeholder-glow" aria-hidden="true" />
        <p className="map-placeholder-eyebrow">map.goldenplate.ca</p>
        <h1 id="map-placeholder-title">Golden Plate Map</h1>
        <p className="map-placeholder-copy">
          The map room is reserved and the table is set. Pins, paths, and a little
          lunchroom cartography will live here soon.
        </p>
        <span className="map-placeholder-status">Placeholder online</span>
      </section>
    </main>
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

function App() {
  if (isMapSubdomain() || isMapPath()) {
    return <MapPlaceholder />
  }

  return <PlateApp />
}

export default App

