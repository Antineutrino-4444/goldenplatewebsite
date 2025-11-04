import React from 'react'
import './App.css'
import { usePlateApp } from '@/hooks/usePlateApp.js'
import LoginView from '@/components/LoginView.jsx'
import InterschoolPortal from '@/components/InterschoolPortal.jsx'
import MainPortal from '@/components/MainPortal.jsx'
import OverlayElements from '@/components/OverlayElements.jsx'
import SchoolRegistration from '@/components/SchoolRegistration.jsx'

function App() {
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

export default App

