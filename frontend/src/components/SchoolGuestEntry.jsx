import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Link from '@/components/SiteLink.jsx'
import './LandingPage.css'

// Use the same guest login and post-auth initialization as the login form.
export default function SchoolGuestEntry({ schoolId, guestLogin }) {
  const navigate = useNavigate()
  const login = useRef(guestLogin)
  const request = useRef(null)
  const [attempt, setAttempt] = useState(0)
  const [failed, setFailed] = useState(false)
  useEffect(() => { login.current = guestLogin }, [guestLogin])
  useEffect(() => {
    let active = true
    setFailed(false)
    const key = `${schoolId}:${attempt}`
    // Reuse the request through StrictMode's effect replay.
    if (request.current?.key !== key) request.current = { key, promise: login.current({ schoolId }) }
    request.current.promise.then((success) => {
      if (!active) return
      if (success) navigate('/portal', { replace: true })
      else setFailed(true)
    })
    return () => { active = false }
  }, [schoolId, attempt, navigate])
  return <main id="main-content" className="auth-page">
    <h1 className="my-6 font-serif text-3xl">{failed ? 'Unable to enter as a guest.' : 'Opening the school portal…'}</h1>
    <p role="status">{failed ? 'The school may be unavailable. You can try again or return to the map.' : 'Signing you in using the school’s guest mode.'}</p>
    <div className="gp-platform-links">{failed && <button className="gp-button" onClick={() => setAttempt((value) => value + 1)}>Try again</button>}<Link className="gp-text-link" to="/map">Back to the school map</Link></div>
  </main>
}
