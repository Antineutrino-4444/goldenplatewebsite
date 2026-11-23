import VideoHelp from '@/components/VideoHelp.jsx'
import InitiativeVideo, { introductionUrl } from '@/components/InitiativeVideo.jsx'
import SchoolCaseStudyNote from '@/components/SchoolCaseStudyNote.jsx'
import { lazy, Suspense, useEffect, useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import Link from '@/components/SiteLink.jsx'
import CommunityCounter from '@/components/CommunityCounter.jsx'
import { ArrowRight, ArrowUpRight, ChevronRight, Mail, Play } from 'lucide-react'
import { PlateMark } from '@/components/PublicHeader.jsx'
import PublicSessionDashboard from '@/components/PublicSessionDashboard.jsx'
import { usePublicSession } from '@/hooks/usePublicSession.js'
import { schoolGuestPath } from '@/lib/schoolMap.js'
import { COMMUNITY_QUOTE, TRADITION_QUOTE } from '@/lib/initiative-writing.js'
import InitiativeContact from '@/components/InitiativeContact.jsx'
import UpdateSubscription from '@/components/UpdateSubscription.jsx'
import './LandingPage.css'

const SchoolGlobe = lazy(() => import('@/components/SchoolGlobe.jsx'))
const CASE_STUDY = '/resources/st-andrews-golden-plate-case-study.pdf'
const REPO = 'https://github.com/Antineutrino-4444/goldenplatewebsite'
const PODCAST = 'https://open.spotify.com/episode/0e3Fu2pkadTsyrRyeFraXe'
const PODCAST_TRANSCRIPT = '/stories/transcript'
const INSTAGRAM = 'https://www.instagram.com/reel/DBgb3-MRESr/'

function ExternalLink({ href, children, className = 'gp-text-link' }) {
  return <a className={className} href={href} target="_blank" rel="noopener noreferrer">
    {children}<ArrowUpRight size={16} aria-hidden="true" />
  </a>
}

function Hero() {
  return <section className="gp-home-opening gp-container" aria-labelledby="home-title">
    <div className="gp-home-spread">
      <div className="gp-home-lead">
        <h1 id="home-title">Students take on school food waste.</h1>
        <p>At St. Andrew’s College, students count clean plates at the dish return. Each week, a winner helps choose Friday’s lunch.</p>
        <div className="gp-home-actions">
          <Link className="gp-button" to="/register">Register your school</Link>
          <Link className="gp-text-link" to="/getting-started">Getting started</Link>
        </div>
      </div>
      <figure className="gp-home-photo">
        <img src="/images/initiative/compost-coaches.webp" alt="Two student Compost Coaches at the dish return as a classmate brings back a plate" width="1600" height="1280" fetchPriority="high" />
        <figcaption>Student Compost Coaches at the dish return in Aurora, Ontario.</figcaption>
      </figure>
    </div>
    <div className="gp-home-byline">
      <Link to="/stories#watch"><Play size={15} aria-hidden="true" />Watch the introduction</Link>
      <a href="#website-updates"><Mail size={16} aria-hidden="true" />Get website updates</a>
    </div>
  </section>
}

const schoolMaterials = [
  {
    to: '/resources#assembly',
    title: 'Assembly slides',
    image: '/images/initiative/student-developers.webp',
    artwork: 'photo',
  },
  {
    to: '/resources#instagram',
    title: 'Winner announcements',
    image: '/images/initiative/golden-plate-winner.webp',
    artwork: 'photo',
  },
  {
    to: '/resources#handouts',
    title: 'One-page school overview',
    image: '/resources/golden-plate-school-overview.webp',
    artwork: 'handout',
  },
]

function SchoolMaterials() {
  return <section className="gp-home-materials gp-container" aria-labelledby="school-materials-title">
    <div className="gp-home-section-heading">
      <h2 id="school-materials-title">Resources for schools</h2>
      <Link className="gp-text-link" to="/resources">Browse all resources</Link>
    </div>
    <div className="gp-home-materials-list">
      {schoolMaterials.map(({ to, title, image, artwork }) => (
        <Link key={to} to={to} className="gp-home-material">
          <div className={`gp-material-image gp-material-${artwork}`}>
            <img src={image} alt="" loading="lazy" />
          </div>
          <div className="gp-material-caption"><h3>{title}</h3></div>
        </Link>
      ))}
    </div>
  </section>
}

function Story({ standalone = false }) {
  const Heading = standalone ? 'h1' : 'h2'
  return <section id="initiative" className={`gp-story gp-container ${standalone ? 'gp-page-intro' : ''}`}>
    <div className="gp-story-copy">
      <p className="gp-section-label">The Students Behind Golden Plate</p>
      <Heading>The award came first.<br />The website followed.</Heading>
      <p>Golden Plate began with a concern familiar to many school communities: food left on plates after lunch. St. Andrew’s Environmental Council, known as the Green Guys, made reducing that waste a shared activity that students could organize and take pride in.</p>
      <p>A clean plate became an entry into a school-wide award draw. Recognition at assembly, a chance to suggest a menu item, and a week of skipping the cafeteria line connected a daily choice with an established school tradition.</p>
      <p>Jiajun (Leo) Li and Shuoyou (Nick) Wang developed PLATE around the practical needs of that initiative. Card identifiers and name searches replaced handwritten tallies, while a shared digital record made it easier to review results over time and bring the process to other schools.</p>
      <figure className="gp-story-quote">
        <blockquote>“{COMMUNITY_QUOTE}”</blockquote>
        <figcaption><strong>Jiajun (Leo) Li</strong> · Golden Plate organizer & PLATE co-developer<br />From his writing on sustainability and school community.</figcaption>
      </figure>
      <Link className="gp-text-link" to="/how-it-works">Explore the initiative <ArrowRight size={16} /></Link>
    </div>
    <figure>
      <img src="/images/initiative/student-developers.webp" alt="Student developers demonstrating the PLATE website on their phones in the dining hall" width="1600" height="1143" loading="lazy" />
      <figcaption>The student-built website, in the room it was made for. Photograph from the St. Andrew’s case study.</figcaption>
    </figure>
  </section>
}

function Impact() {
  return <section className="gp-impact gp-container" aria-labelledby="impact-title">
    <div className="gp-impact-copy">
      <h2 id="impact-title">What changed at St. Andrew’s?</h2>
      <p>The case study describes more awareness of portions, closer relationships with kitchen staff, and a rise in clean-plate rates.</p>
      <ExternalLink href={CASE_STUDY}>Read the case study</ExternalLink>
      <SchoolCaseStudyNote />
    </div>
    <div className="gp-impact-data">
      <dl>
        <div><dt>Before the initiative</dt><dd>Below 50%</dd></div>
        <div><dt>Reported high after launch</dt><dd>75%</dd></div>
      </dl>
      <p>Clean-plate rates reported in the St. Andrew’s case study.</p>
    </div>
  </section>
}

function HowItWorks({ standalone = false }) {
  const Heading = standalone ? 'h1' : 'h2'
  return <section className={`gp-how gp-container ${standalone ? 'gp-page-intro' : ''}`}>
    <div className="gp-page-heading">
      <Heading>How Golden Plate works.</Heading>
      <p>A student-led lunch initiative turns reducing food waste into a shared school tradition. Students, staff mentors, and food services work together to connect everyday choices with recognition and collective responsibility.</p>
    </div>
    <ol className="gp-steps">
      <li><h2>Make the daily choice visible</h2><div><p>Students choose portions they can finish. At the dish return, student Compost Coaches record plate categories during the school’s chosen lunch sessions.</p><p>The aim is to make thoughtful food choices part of ordinary school life, with students leading the conversation and shaping the program.</p></div></li>
      <li><h2>Recognize participation</h2><div><p>At St. Andrew’s, students with a clean plate can enter a draw for the Golden Plate award. Winners are recognized at assembly, can skip the cafeteria line for a week, and can propose a menu item.</p><p>Each school can agree on an appropriate routine and reward with its student team, staff mentor, and food services. The tradition should reflect the community taking part.</p></div></li>
      <li><h2>Learn from the record</h2><div><p>PLATE supports the initiative with a consistent record of lunch sessions, student participation, and plate categories. Dashboards, house rankings, and live counters help schools share their progress.</p><p>Students can use the results and feedback from their peers to refine the program.</p></div></li>
    </ol>
    <VideoHelp videos={[3, 7, 32]} label="Watch the school routine" /><div className="gp-how-guide"><h2>Ready to use the website?</h2><p>Find out how to register, gather a student team, and plan your first lunch.</p><Link className="gp-text-link" to="/getting-started">Get started at your school <ArrowRight size={16} /></Link></div>
  </section>
}

function Platform() {
  const result = usePublicSession()
  return <section className="gp-platform gp-container" aria-labelledby="platform-title">
    <div className="gp-platform-intro">
      <p className="gp-section-label">PLATE · The Recording Website</p>
      <h2 id="platform-title">Schools are using PLATE.</h2>
      <p>Record plates, review lunch totals, and run your school’s Golden Plate draws. Explore a session below to see PLATE in use.</p>
    </div>
    <div className="gp-platform-body">
      <div className="gp-platform-artifact">
        <div className="gp-session-provenance"><p><strong>{result.session ? 'A public school session' : 'Explore a public school session'}</strong><span>{result.session ? 'Lunch totals from a participating school.' : 'See how a participating school records its lunch in PLATE.'}</span></p></div>
        <PublicSessionDashboard result={result} />
        <div className="gp-platform-links">{result.session && <Link className="gp-button" to={`/guest/sessions/${encodeURIComponent(result.session.session_id)}`}>Explore this session <ArrowRight size={17} /></Link>}<ExternalLink href={REPO}>Source code & documentation</ExternalLink></div>
      </div>
      <dl className="gp-feature-list">
        <div><dt>For Compost Coaches</dt><dd>Search part of a name or scan a student card’s identifier. Record plate categories against imported student and staff rosters.</dd></div>
        <div><dt>For school leads</dt><dd>Manage sessions, accounts, and access. Review dashboards and download CSV records.</dd></div>
        <div><dt>For assemblies</dt><dd>Show the live counter, house rankings, and draw results.</dd></div>
        <div><dt>For guests</dt><dd>View public school sessions without an account.</dd></div>
      </dl>
    </div>
  </section>
}

function LiveCounterFeature() {
  return <section id="live-counter" className="gp-counter" aria-labelledby="counter-title">
    <div className="gp-container">
      <div className="gp-counter-intro"><h2 id="counter-title">Community live counter</h2>
        <p>Clean plates recorded by students and faculty across all schools using PLATE.</p>
      </div>
      <div className="gp-counter-live"><p>Across all schools · All time</p><CommunityCounter compact /></div>
    </div>
  </section>
}

function Community() {
  const [schools, setSchools] = useState([])
  const [status, setStatus] = useState('loading')
  const [selected, setSelected] = useState(null)
  useEffect(() => {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), 8000)
    fetch('/api/map/schools', { signal: controller.signal })
      .then((r) => { if (!r.ok) throw new Error(); return r.json() })
      .then((data) => { setSchools(Array.isArray(data.schools) ? data.schools : []); setStatus('ready') })
      .catch(() => setStatus('error')).finally(() => clearTimeout(timer))
    return () => { controller.abort(); clearTimeout(timer) }
  }, [])
  return <section className="gp-community gp-container" aria-labelledby="community-title">
    <div>
      <h2 id="community-title">Find another school.</h2>
      <p>Drag the globe to explore. Select a school pin to see its public sessions.</p>
      <div className="gp-community-status" aria-live="polite">
        {selected ? <Link className="gp-community-school-link" to={schoolGuestPath(selected)}><strong>{selected.name}</strong><span>{selected.code} · {selected.address || selected.location_name}</span><span className="gp-text-link">Open guest view <ArrowRight size={15} /></span></Link> : <strong>{status === 'ready' ? `${schools.length} participating ${schools.length === 1 ? 'school' : 'schools'}` : status === 'error' ? 'School list unavailable here. Try the full map.' : 'Loading schools…'}</strong>}
      </div>
      <Link className="gp-text-link" to="/map">Open the school map <ArrowRight size={16} /></Link>
    </div>
    <div className="gp-community-globe">
      <Suspense fallback={<p className="gp-globe-placeholder">Loading globe…</p>}><SchoolGlobe schools={schools} onSelect={setSelected} /></Suspense>
      <p className="gp-globe-caption">Public school locations · Natural Earth</p>
    </div>
  </section>
}

function Media({ standalone = false }) {
  const Heading = standalone ? 'h1' : 'h2'
  const [instagram, setInstagram] = useState(false)
  return <section id="watch" className={`gp-media gp-container ${standalone ? 'gp-page-intro' : ''}`}>
    <div className="gp-media-heading"><Heading>From the dining hall.</Heading><p>Watch the introduction, hear from the students, or catch up with the Environmental Council.</p></div>
    <div className="gp-media-grid">
      <article className="gp-video-feature">
        <InitiativeVideo />
        <div className="gp-media-title"><h3>How the Golden Plate works</h3><ExternalLink href={introductionUrl}>YouTube</ExternalLink></div>
      </article>
      <article id="podcast" className="gp-podcast">
        <p className="gp-section-label">Podcast · Second Harvest National Youth Council</p>
        <h3>Spoiler Alert:<br />The Golden Plate</h3>
        <p>Jiajun (Leo) Li, Shuoyou (Nick) Wang, and Michael Casey trace Golden Plate from paper tallies to card scans, student-led assemblies, and a website other schools can use.</p>
        <div className="gp-spotify-player"><iframe title="Spoiler Alert podcast — S2 E02 The Golden Plate" src="https://open.spotify.com/embed/episode/0e3Fu2pkadTsyrRyeFraXe?utm_source=generator&theme=0" height="232" loading="lazy" allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" /></div>
        <div className="gp-podcast-links"><ExternalLink href={PODCAST}>Listen on Spotify</ExternalLink><Link className="gp-text-link" to={PODCAST_TRANSCRIPT}>Read the edited transcript <ArrowRight size={16} /></Link></div>
      </article>
    </div>
    <VideoHelp videos={[1, 2, 7, 27]} label="Using PLATE? Watch the school video guides" />
    <div className="gp-social-grid">
      <article className="gp-instagram">
        <div className="gp-instagram-header"><h3>The winners chose grilled cheese.</h3><ExternalLink href="https://www.instagram.com/envirocouncil_sac/">@envirocouncil_sac</ExternalLink></div>
        {instagram ? <iframe className="gp-instagram-embed" title="SAC Environmental Council — Golden Plate winners choose Friday lunch" src="https://www.instagram.com/reel/DBgb3-MRESr/embed/" loading="lazy" height="570" allow="encrypted-media; fullscreen; picture-in-picture" /> : <div className="gp-instagram-preview"><img src="/images/initiative/golden-plate-winner.webp" alt="A Golden Plate winner beside the meal station and award display at St. Andrew’s" width="707" height="631" loading="lazy" /><div><p>One Friday menu, chosen by Golden Plate winners. The council’s reel shows how the reward becomes part of school life.</p><button className="gp-text-link" onClick={() => setInstagram(true)}>Load the Instagram reel <ArrowRight size={16} /></button></div></div>}
        {instagram && <button className="gp-text-link gp-embed-close" onClick={() => setInstagram(false)}>Close embedded reel</button>}
        <ExternalLink href={INSTAGRAM}>View the original reel</ExternalLink>
      </article>
      <aside className="gp-coverage">
        <h3>Elsewhere</h3>
        <a href="https://www.theibsc.org/news/stories/friendship" target="_blank" rel="noopener noreferrer"><span>International Boys’ Schools Coalition</span><strong>A shared lunch tradition builds connection.</strong><ArrowUpRight size={18} /></a>
        <a href="https://www.linkedin.com/posts/the-green-schools-alliance_sustainableschools-greenschools-teachers-activity-7375757042549972992--T7C" target="_blank" rel="noopener noreferrer"><span>Green Schools Alliance</span><strong>St. Andrew’s College tackles food waste.</strong><ArrowUpRight size={18} /></a>
        <a href="https://thesustainableschool.beehiiv.com/p/sustainable-school-newsletter-let-s-eat-55fa70ca5798ec89" target="_blank" rel="noopener noreferrer"><span>The Sustainable School Newsletter</span><strong>The Golden Plate playbook.</strong><ArrowUpRight size={18} /></a>
      </aside>
    </div>
  </section>
}

function StudentVoice() {
  return <section id="student-perspective" className="gp-student-voice gp-container" aria-label="A student perspective">
    <div><p className="gp-section-label">A Student Perspective</p><blockquote>“{TRADITION_QUOTE}”</blockquote><p>Jiajun (Leo) Li<span>From his writing on sustainability and school community.</span></p><p className="gp-student-reflection">Golden Plate gave students a practical way to shape school culture together. In Jiajun’s account, recognition and shared responsibility helped turn an environmental concern into a tradition their peers wanted to take part in.</p></div>
    <figure><img src="/images/initiative/middle-school-green-team.webp" alt="The Middle School Green Team learning from senior student leaders and celebrating the Golden Plate" width="800" height="600" loading="lazy" /><figcaption>Senior students help the Middle School Green Team become Compost Coaches.</figcaption></figure>
  </section>
}

function Join() {
  return <section className="gp-join gp-container">
    <div><h2>Bring it to your school.</h2><p>Plan your first lunch with student volunteers, a staff mentor, and your food services team.</p><Link className="gp-text-link" to="/getting-started">Plan your first lunch <ArrowRight size={16} /></Link></div>
    <div className="gp-join-actions"><Link className="gp-button" to="/register">Register your school <ArrowRight size={17} /></Link><Link className="gp-text-link" to="/login">School login <ArrowRight size={16} /></Link></div>
  </section>
}

export function PublicFooter() {
  return <footer className="gp-footer"><div className="gp-container">
    <div className="gp-footer-top">
      <Link to="/" className="public-brand"><PlateMark /><span>golden plate<span className="brand-caption">Student-Led Food Waste Prevention</span></span></Link>
      <nav aria-label="Footer navigation">
        <div><strong>For schools</strong><Link to="/getting-started">Getting started</Link><Link to="/resources">School resources</Link><Link to="/register">School registration</Link><Link to="/login">School login</Link></div>
        <div><strong>The initiative</strong><Link to="/about">Our story</Link><Link to="/how-it-works">How it works</Link><Link to="/stories">Watch &amp; listen</Link><Link to="/how-it-works#contact">Contact</Link></div>
        <div><strong>Website tools</strong><Link to="/map">School map</Link><Link to="/live-counter/community">Live counter</Link><Link to="/website-guide">Full website guide</Link><Link to="/website-guide#video-library">Video guides</Link><Link to="/release-notes">Release history</Link></div>
      </nav>
    </div>
    <div className="gp-footer-bottom"><span>PLATE — Prevention, Logging & Assessment of Tossed Edibles</span><div><a href="/privacy">Privacy policy</a><a href="/terms">Terms of service</a><Link to="/#website-updates">Get website updates</Link><Link to="/resources#handouts">Case study &amp; photo source</Link><ExternalLink href={REPO}>GitHub</ExternalLink></div></div>
  </div></footer>
}

function Questions() {
  return <section className="gp-faq gp-container"><h2>Before you start</h2>
    <details><summary>Who can bring Golden Plate to a school?<ChevronRight size={18} /></summary><p>Students, teachers, and food services teams can work together to lead a program. Ask a staff mentor to help organize your team and submit your school registration.</p></details>
    <details><summary>Do we need special equipment?<ChevronRight size={18} /></summary><p>You can start with a simple tally. PLATE adds digital recording, roster uploads, dashboards, and exports. Barcode scanners are supported but optional.</p></details>
    <details><summary>How do school accounts work?<ChevronRight size={18} /></summary><p>Register your school for approval, or use an existing school invite. Once your school is set up, request an account with its school code. School administrators manage access.</p></details>
    <details><summary>Can we see results without an account?<ChevronRight size={18} /></summary><p>The school map is public. You can also use read-only guest access from the login page with a school code. Schools control how student details appear to guests.</p></details>
  </section>
}

const titles = { home: 'Golden Plate — Student-Led Food Waste Prevention', about: 'Our story · Golden Plate', how: 'How it works · Golden Plate', stories: 'Watch & listen · Golden Plate' }
const movedHomeSections = { '#initiative': '/about', '#watch': '/stories', '#podcast': '/stories' }

export default function LandingPage({ page = 'home' }) {
  const location = useLocation()
  const movedSection = page === 'home' && movedHomeSections[location.hash]
  useEffect(() => { document.title = titles[page] }, [page])
  if (movedSection) return <Navigate to={movedSection + location.search + location.hash} replace state={location.state} />
  return <div key={page} className="golden-public"><main id="main-content" tabIndex={-1}>
    {page === 'home' && <><Hero /><SchoolMaterials /><LiveCounterFeature /><Community /><div className="gp-container"><UpdateSubscription /></div></>}
    {page === 'about' && <><Story standalone /><Impact /><StudentVoice /><Community /></>}
    {page === 'how' && <><HowItWorks standalone /><Platform /><StudentVoice /><InitiativeContact /><Questions /></>}
    {page === 'stories' && <><Media standalone /><StudentVoice /></>}
    {page !== 'home' && <Join />}
  </main><PublicFooter /></div>
}
