import { useEffect } from 'react'
import { useTheme } from 'next-themes'
import { Navigate, useLocation } from 'react-router-dom'
import Link from '@/components/SiteLink.jsx'
import { PublicFooter } from '@/components/LandingPage.jsx'
import SocialPostTemplates from '@/components/SocialPostTemplates.jsx'
import SchoolCaseStudyNote from '@/components/SchoolCaseStudyNote.jsx'
import './SchoolResourcesPage.css'

function SchoolHandouts({ theme }) {
  const suffix = theme === 'dark' ? '-dark' : ''
  const overview = '/resources/golden-plate-school-overview' + suffix
  return <section id="handouts" className="gp-school-handouts gp-container" aria-labelledby="handouts-title">
    <h2 id="handouts-title">School Handouts</h2>
    <div className="gp-handout-columns">
      <article className="gp-one-sheet">
        <a className="gp-handout-thumb" href={overview + '.pdf'} target="_blank" rel="noopener noreferrer" aria-label={'Preview ' + theme + ' school overview PDF'}>
          <img src={overview + '.webp'} alt="" width="700" height="906" loading="lazy" />
        </a>
        <div>
          <h3>One-page school overview</h3>
          <p>A one-page introduction to share with teachers and school leaders.</p>
          <a className="gp-text-link" href={overview + '.pdf'} download>Download PDF</a>
        </div>
      </article>
      <article className="gp-case-study">
        <h3>St. Andrew’s College case study</h3>
        <SchoolCaseStudyNote />
        <a className="gp-text-link" href="/resources/st-andrews-golden-plate-case-study.pdf" target="_blank" rel="noopener noreferrer">Read the original PDF</a>
      </article>
    </div>
  </section>
}

function SchoolResources() {
  const { resolvedTheme } = useTheme()
  const theme = resolvedTheme === 'dark' ? 'dark' : 'light'
  useEffect(() => { document.title = 'School Resources · Golden Plate' }, [])
  return <div className="golden-public gp-school-resources">
    <main id="main-content" tabIndex={-1}>
      <header className="gp-resource-header gp-container"><h1>School Resources</h1></header>
      <section className="gp-assembly-entry gp-container" aria-labelledby="assembly-entry-title">
        <div>
          <h2 id="assembly-entry-title">School assembly slides</h2>
          <p>Share your school’s clean-plate results in PowerPoint, Google Slides, or a PDF.</p>
          <Link className="gp-button" to="/export">Export assembly slides</Link>
        </div>
        <img src={'/resources/school-results-' + theme + '.webp'} alt="Example assembly results slide" width="960" height="540" />
      </section>
      <SocialPostTemplates />
      <SchoolHandouts theme={theme} />
      <div className="gp-resource-join gp-container"><Link className="gp-button" to="/register">Register your school</Link></div>
    </main>
    <PublicFooter />
  </div>
}

export default function SchoolResourcesPage() {
  const { hash, search, state } = useLocation()
  const query = new URLSearchParams(search)
  const oldExportOptions = ['format', 'presentation', 'theme', 'school', 'live_error'].some(key => query.has(key))
  if (hash === '#assembly' || (!hash && oldExportOptions)) {
    return <Navigate replace to={{ pathname: '/export', search }} state={state} />
  }
  return <SchoolResources />
}
