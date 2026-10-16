import { dashboardMetrics } from '@/lib/session-metrics.js'
import SessionMetrics from '@/components/SessionMetrics.jsx'

export default function PublicSessionDashboard({ result }) {
  const { session, status, retry } = result
  if (status !== 'ready') {
    return <div className="gp-session-state" role="status" aria-live="polite">
      <p>{status === 'loading' ? 'Loading a session directly from PLATE…'
        : status === 'empty' ? 'There are no public sessions to show yet.'
        : status === 'unavailable' ? 'This session is no longer available to guests.'
        : 'The session could not be loaded. Please try again.'}</p>
      {(status === 'error' || status === 'unavailable') && <button className="gp-text-link" onClick={retry}>Try again</button>}
    </div>
  }
  return <div className="gp-session-dashboard">
    <div className="gp-session-heading"><h3>Session Dashboard</h3><p>{session.school_name} · Read-only guest view</p></div>
    <SessionMetrics sessionName={session.session_name} sessionDashboardStats={dashboardMetrics(session)}
      status={session.status} updatedAt={session.updated_at} />
  </div>
}
