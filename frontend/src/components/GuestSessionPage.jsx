import { useEffect } from 'react'
import { useParams } from 'react-router-dom'
import Link from '@/components/SiteLink.jsx'
import PublicSessionDashboard from '@/components/PublicSessionDashboard.jsx'
import { usePublicSession } from '@/hooks/usePublicSession.js'
import './LandingPage.css'

export default function GuestSessionPage() {
  const { sessionId } = useParams()
  const result = usePublicSession(sessionId)
  useEffect(() => {
    document.title = 'Guest session dashboard · Golden Plate'
  }, [sessionId])
  return <div className="golden-public">
    <main id="main-content" className="gp-container gp-guest-session">
      <p className="gp-section-label">PLATE · Guest access</p>
      <h1>A look at lunch.</h1>
      <p className="gp-guest-intro">This is the session you opened from the website. View its latest saved totals without an account.</p>
      <PublicSessionDashboard result={result} />
      <p className="gp-session-source">Loaded directly from PLATE, the school recording website. Guest access is read-only; student and staff details are not included.</p>
      <div className="gp-platform-links"><button className="gp-text-link" onClick={result.retry} disabled={result.status === 'loading'}>Refresh this session</button><Link className="gp-text-link" to="/">Back to the initiative</Link><Link className="gp-text-link" to="/login">School login</Link></div>
    </main>
  </div>
}
