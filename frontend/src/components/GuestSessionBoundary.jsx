import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { guestPageScope, guestSession, shouldEndGuestSession } from '@/lib/guest-session.js'

export default function GuestSessionBoundary({ children }) {
  const { pathname } = useLocation()
  const previousPath = useRef(null)
  const pendingExit = useRef(null)
  const [readyPath, setReadyPath] = useState(null)
  const waiting = readyPath !== pathname && (pendingExit.current || shouldEndGuestSession(previousPath.current, pathname))

  useLayoutEffect(() => {
    let active = true
    const needsExit = shouldEndGuestSession(previousPath.current, pathname)
    previousPath.current = pathname
    const request = needsExit ? guestSession.leave() : pendingExit.current
    if (!request) { setReadyPath(pathname); return }
    pendingExit.current = request
    request.then(() => {
      if (!active) return
      pendingExit.current = null
      setReadyPath(pathname)
    })
    return () => { active = false }
  }, [pathname])

  useEffect(() => {
    if (!guestPageScope(pathname)) return
    const leavePage = () => {
      // Closing the tab or leaving the site may not allow a normal request to
      // finish. This endpoint only clears guests, never a school account.
      if (navigator.sendBeacon?.('/api/auth/guest/logout')) return
      fetch('/api/auth/guest/logout', { method: 'POST', keepalive: true }).catch(() => {})
    }
    window.addEventListener('pagehide', leavePage)
    return () => window.removeEventListener('pagehide', leavePage)
  }, [pathname])

  return waiting ? <div className="min-h-screen flex items-center justify-center bg-[var(--site-paper)] text-sm text-[var(--site-muted)]" role="status">Leaving guest view…</div> : children
}
