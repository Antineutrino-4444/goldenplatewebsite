import VideoHelp from '@/components/VideoHelp.jsx'
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
      <p className="gp-guest-intro">View this school’s recorded lunch totals without an account.</p>
      <PublicSessionDashboard result={result} />
      <VideoHelp videos={[14, 25]} label="Video help with public results" />
      <div className="gp-platform-links"><button className="gp-text-link" onClick={result.retry} disabled={result.status === 'loading'}>Refresh this session</button><Link className="gp-text-link" to="/">Back to the initiative</Link><Link className="gp-text-link" to="/login">School login</Link></div>
    </main>
  </div>
}
