import { useEffect } from 'react'
import { Link as RouterLink, useLocation } from 'react-router-dom'
import Link from '@/components/SiteLink.jsx'
import { PublicFooter } from '@/components/LandingPage.jsx'
import InitiativeContact from '@/components/InitiativeContact.jsx'
import './LandingPage.css'

const chapters = [
  ['register-school', 'Register a school'], ['join-school', 'Join your school'],
  ['sign-in', 'Sign in & check access'], ['prepare-rosters', 'Prepare your rosters'],
  ['create-session', 'Start a lunch session'], ['record-plates', 'Record plates'],
  ['review-results', 'Review results & draws'], ['share-results', 'Share & display results'],
]

function ChapterLink({ to, children }) {
  const location = useLocation()
  return <RouterLink to={to} state={location.state} replace preventScrollReset>{children}</RouterLink>
}

function GuideStep({ index, children }) {
  const [id, title] = chapters[index]
  return <section id={id} className="gp-guide-step" aria-labelledby={`${id}-title`}><h2 id={`${id}-title`}><span>{String(index + 1).padStart(2, '0')}</span>{title}</h2>{children}</section>
}

export default function GettingStartedPage() {
  useEffect(() => { document.title = 'Getting started with PLATE · Golden Plate' }, [])
  return <div className="golden-public"><main id="main-content">
    <header className="gp-guide-intro gp-container"><p className="gp-section-label">The website guide</p><h1>Getting started with PLATE.</h1><p>From registering a school to recording your first lunch session. Follow the steps for your role; if your school already uses PLATE, begin with joining its existing account system.</p><div className="gp-platform-links"><Link className="gp-button" to="/register">Register a school →</Link><Link className="gp-text-link" to="/signup">Request a school account →</Link><Link className="gp-text-link" to="/login">School login →</Link></div><p className="gp-guide-overview-link">For the initiative’s purpose, rewards, and school routine, read <Link to="/how-it-works">How Golden Plate works</Link>.</p></header>
    <div className="gp-guide-layout gp-container">
      <nav className="gp-guide-contents" aria-label="Guide contents"><h2>In this guide</h2><ol>{chapters.map(([id, title], index) => <li key={id}><ChapterLink to={`#${id}`}><span>{index + 1}.</span>{title}</ChapterLink></li>)}</ol><ChapterLink to="#contact">Questions? Contact the team ↓</ChapterLink></nav>
      <div className="gp-guide-body">
        <GuideStep index={0}>
          <p>One person should register a new school. If your school already has a PLATE code, go to <ChapterLink to="#join-school">Join your school</ChapterLink> instead.</p>
          <ol><li>Open <Link to="/register">Register a school</Link> and enter a contact email you can access. Select <strong>Send Code</strong>.</li><li>Enter the six-digit code from your email and select <strong>Verify Code</strong>. If it expires, request another code; check spam or junk if it does not arrive.</li><li>Enter your school name and, optionally, a shareable school code. Leaving the code blank lets the system generate one.</li><li>Complete the primary administrator’s display name, username, and password, then submit the registration request.</li><li>Wait for PLATE administrator approval before trying to use the new school account. Keep the username and password you chose.</li></ol>
          <p>If you have specifically been given a <strong>Legacy Invite</strong> for school registration, use that method and follow the invite fields instead of the standard email-verification route.</p>
        </GuideStep>
        <GuideStep index={1}>
          <p>Ask your school administrator for the school code. A school code identifies the school; it does not automatically approve a new member.</p>
          <ol><li>Open <Link to="/signup">Request a school account</Link> and choose <strong>School Code</strong>.</li><li>Enter your full name, choose a username and password, and enter the school code.</li><li>Select <strong>Submit Request</strong>. Your school administrator reviews the request before you can sign in.</li></ol>
          <p><strong>For school administrators:</strong> open <strong>Admin Panel → Account Requests</strong> to review pending member requests. Only approve people who should have access to your school.</p>
          <p>If an administrator gave you a one-time account invite, choose <strong>Legacy Invite</strong> and enter that invite code for immediate access. School-registration invites and member-account invites belong to their respective forms.</p>
        </GuideStep>
        <GuideStep index={2}>
          <p>Open <Link to="/login">School login</Link>, enter your approved account’s username and password, and select <strong>Login</strong>. Confirm the school name and code in the portal header before recording.</p>
          <p>Guest access ends automatically when you leave the school portal. If a sign-up page says you are still signed in, select <strong>Log out and continue</strong>. You can also choose <strong>Account menu → Log out</strong> before switching to your regular account.</p>
          <dl className="gp-guide-roles"><div><dt>School superadmin</dt><dd>Manages school access and settings, including the school contact email and map-location choice.</dd></div><div><dt>Admin</dt><dd>Can upload student and teacher databases, manage school accounts, and manage draws.</dd></div><div><dt>Member / Compost Coach</dt><dd>Records plates and reviews sessions using the access provided by the school.</dd></div><div><dt>Guest</dt><dd>Uses the normal portal in read-only mode. Guests cannot record plates or perform administrator actions.</dd></div></dl>
          <p>The Recorder starts with the recording area and Plate Tracking History. Select House rankings, Draw Center, or, for administrators, Student and teacher databases to open that panel below the recording area. Select the same control again to close it. History always stays available. Use Expand all to show every panel and Collapse all to return to the compact view.</p>
          <p>If a control is unavailable, check whether you are signed in as a guest or ask your school administrator about your account’s role.</p>
        </GuideStep>
        <GuideStep index={3}>
          <p><strong>For admins and superadmins.</strong> Open <strong>Student and teacher databases</strong> on the Recorder page. In the relevant database, select <strong>Choose file</strong>. Use <strong>Preview Database</strong> to check the saved list. Replacing an existing database requires confirmation.</p>
          <h3>Student CSV</h3><p>Include <strong>Student ID</strong>, <strong>Last</strong>, and <strong>Preferred</strong>. You can use <strong>First</strong> if there is no Preferred column. Column order and capitalization do not matter. Grade, Advisor, House, and Clan are optional and may be blank.</p><pre aria-label="Student CSV example"><code>{'Student ID,Last,Preferred,Grade,Advisor,House,Clan\nDEMO-001,Example,Avery,,,,'}</code></pre><p className="gp-guide-file-note">This row is fictional. Replace it with your school’s roster before uploading.</p><a className="gp-text-link" href="/resources/plate-student-roster-template.csv" download>Download the student CSV template ↓</a>
          <h3>Teacher database</h3><p>Upload a CSV or comma-separated TXT file with Last and Preferred, or First when Preferred is absent. Include a stable Faculty ID to identify the same person after a name change. Column order and capitalization do not matter. Files without the required name headers are rejected. You can also edit a name in the teacher preview; past records and draw results will display the updated name while retaining the original name in history.</p><a className="gp-text-link" href="/resources/plate-teacher-roster-template.csv" download>Download the teacher CSV template ↓</a><p>Keep student IDs consistent with the identifiers on cards you plan to scan. Roster membership affects draw eligibility: students missing from the replacement roster are excluded from ticket draws.</p>
        </GuideStep>
        <GuideStep index={4}>
          <ol><li>Open the <strong>Recorder</strong> page. If no session is selected, choose <strong>Create New Session</strong>; otherwise select <strong>New Session</strong> above the recording area.</li><li>Enter a session name or leave it blank for the default name. Select <strong>Create Session</strong>.</li><li>Check the session shown below the recording buttons. Use <strong>Switch Session</strong> to choose an existing session instead.</li></ol>
          <p>Have your coaches confirm the intended session before lunch begins. New records are added to the currently selected session.</p>
        </GuideStep>
        <GuideStep index={5}>
          <p>Under <strong>Add a plate record</strong>, select the plate category. Use the same category definitions across your team.</p>
          <dl className="gp-guide-roles"><div><dt>Clean plate</dt><dd>Use CLEAN PLATE for a student’s clean plate.</dd></div><div><dt>Faculty clean</dt><dd>Use FACULTY CLEAN for a staff member’s clean plate.</dd></div><div><dt>Dirty plate</dt><dd>Use DIRTY PLATE for a plate with leftover food.</dd></div><div><dt>Very dirty plate</dt><dd>Use VERY DIRTY PLATE when it meets your team’s agreed definition for substantial leftovers.</dd></div></dl>
          <ol><li>In the category dialog, enter the student ID, scan a compatible student-card identifier, or type part of the name and select the correct match. For faculty clean plates, use the faculty-name field.</li><li>Select the dialog’s record button, or press Enter. Wait for the save confirmation.</li><li>Check the totals and <strong>Plate Tracking History</strong> to confirm the category and record before moving on.</li></ol>
          <p>You can leave the identity field blank to add one plate to the count. This creates a count-only record rather than an identified student entry for a draw. If the connection fails after submission, check history before retrying so the same plate is not recorded twice.</p>
        </GuideStep>
        <GuideStep index={6}>
          <p>Open <strong>Dashboard</strong> or <Link to="/portal/dashboard">Session dashboard</Link> to review the selected session’s totals. Use the Recorder’s history and house rankings to inspect the underlying activity, and <strong>Switch Session</strong> to review another lunch.</p>
          <h3>Running the award draw</h3><p>Admins and superadmins use <strong>Draw Center</strong>. Review the eligible students and ticket standings, select <strong>Start Draw</strong>, review the selected candidate, then select <strong>Finalize Winner</strong> when the result is ready. The faculty picker has its own pick and finalization controls.</p><p>Check roster membership and exclusions before the draw. Count-only entries do not identify a student, and session settings and eligibility rules determine who can take part. The draw history records the actions taken.</p>
          <p>Signed-in members can use the available CSV download controls to review records outside the website. Guests do not have export access. Administrators also have school session export tools in their administration area.</p>
        </GuideStep>
        <GuideStep index={7}>
          <ul><li><strong>School display:</strong> open <Link to="/live-counter">Live counter</Link> from the portal for your school’s display and available time-range settings.</li><li><strong>Initiative-wide display:</strong> the <Link to="/live-counter/community">all-schools counter</Link> shows the combined clean-plate and session totals across PLATE.</li><li><strong>Guest access:</strong> visitors can select a school pin on the <Link to="/map">school map</Link> and open its popup, or use <strong>Continue as Guest</strong> on the login page with a school code. This signs the browser into that school’s existing guest mode. To record again, choose <strong>Account menu → Log out</strong>, then sign in with your regular account.</li><li><strong>School location:</strong> use <strong>Account menu → School location</strong> to review the school’s location. The school superadmin can save a location or choose to remain unmapped. Unmapped schools are listed in Others.</li></ul>
          <p>Guests see sessions made public by the school, with the school’s guest-privacy settings applied. Use the portal’s top-bar links to return to the map or live counter.</p>
        </GuideStep>
        <section className="gp-guide-troubleshooting" aria-labelledby="guide-help"><h2 id="guide-help">If something does not look right</h2><dl><div><dt>Account request still pending?</dt><dd>Ask your school administrator to review it. Registering a school and requesting a member account are separate approvals.</dd></div><div><dt>A student cannot be found?</dt><dd>Ask an admin to check the student database, ID, and Preferred/First name fields. Select a matching result rather than assuming similarly spelled names refer to the same person.</dd></div><div><dt>Totals appear in the wrong session?</dt><dd>Check the selected session and Plate Tracking History. Ask a school administrator to review any correction before continuing.</dd></div></dl><p>For initiative or website questions, contact Matthew Jaekel or the SAC office below.</p></section>
      </div>
    </div>
    <InitiativeContact showGuideLink={false} />
  </main><PublicFooter /></div>
}
