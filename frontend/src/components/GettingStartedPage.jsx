import { useEffect } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { BookOpen } from 'lucide-react'
import InitiativeVideo, { introductionUrl } from '@/components/InitiativeVideo.jsx'
import Link from '@/components/SiteLink.jsx'
import { PublicFooter } from '@/components/LandingPage.jsx'
import './LandingPage.css'
import './GettingStartedPage.css'

function SchoolQuickStart() {
  useEffect(() => { document.title = 'Get started at your school · Golden Plate' }, [])

  return <div className="golden-public">
    <main id="main-content" className="gp-container gp-start" tabIndex={-1}>
      <header className="gp-start-intro">
        <div className="gp-start-copy">
          <h1>Bring Golden Plate to your school</h1>
          <p>Choose one person to register your school. They’ll need the school name and a contact email they can verify.</p>
          <div className="gp-start-actions">
            <Link className="gp-button" to="/register">Register your school</Link>
            <Link className="gp-text-link" to="/website-guide"><BookOpen size={17} aria-hidden="true" />Full website guide</Link>
          </div>
        </div>
        <figure className="gp-start-video">
          <InitiativeVideo />
          <figcaption>The Golden Plate team at St. Andrew’s College. <a href={introductionUrl} target="_blank" rel="noopener noreferrer">Watch on YouTube</a></figcaption>
        </figure>
      </header>

      <section className="gp-start-plan" aria-label="Plan your first lunch">
        <h2>From sign-up to your first lunch</h2>
        <ol>
          <li>
            <h3>Register your school</h3>
            <p>One person verifies a contact email, enters the school name, and requests the first administrator account. The Golden Plate team reviews the request.</p>
          </li>
          <li>
            <h3>Gather your team</h3>
            <p>Bring together a staff mentor, student volunteers, and someone from food services. Choose a lunch date and how you’ll recognize participation.</p>
            <Link className="gp-text-link" to="/resources">Assembly slides and examples</Link>
          </li>
          <li>
            <h3>Run one lunch</h3>
            <p>Once your school is approved, sign in and start a lunch session. Have student volunteers record plates at the dish return, then share the result with classmates.</p>
          </li>
        </ol>
      </section>

      <nav className="gp-start-support" aria-label="Help for registered schools">
        <h2>Already part of Golden Plate?</h2>
        <div>
          <Link className="gp-text-link" to="/login">School login</Link>
          <Link className="gp-text-link" to="/signup">Join your school</Link>
        </div>
      </nav>
    </main>
    <PublicFooter />
  </div>
}

export default function GettingStartedPage() {
  const { search, hash, state } = useLocation()
  // The former handbook lived here. Keep bookmarks to its sections working.
  if (hash && hash !== '#main-content' && !hash.startsWith('#:~:text=')) {
    return <Navigate to={{ pathname: '/website-guide', search, hash }} state={state} replace />
  }
  return <SchoolQuickStart />
}
