import { useEffect, useState } from 'react'
import Link from '@/components/SiteLink.jsx'
import { PublicFooter } from '@/components/LandingPage.jsx'
import PresentationDownloads from '@/components/PresentationDownloads.jsx'
import SocialPostTemplates from '@/components/SocialPostTemplates.jsx'
import SchoolCaseStudyNote from '@/components/SchoolCaseStudyNote.jsx'
import './SchoolResourcesPage.css'

function SchoolHandouts() {
  const [theme, setTheme] = useState('light')
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
          <div className="gp-pdf-theme">
            <label htmlFor="school-overview-theme">PDF theme</label>
            <select id="school-overview-theme" value={theme} onChange={(event) => setTheme(event.target.value)}>
              <option value="light">Light</option><option value="dark">Dark</option>
            </select>
          </div>
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

export default function SchoolResourcesPage() {
  useEffect(() => { document.title = 'School Resources · Golden Plate' }, [])
  return <div className="golden-public gp-school-resources">
    <main id="main-content" tabIndex={-1}>
      <header className="gp-resource-header gp-container"><h1>School Resources</h1></header>
      <PresentationDownloads />
      <SocialPostTemplates />
      <SchoolHandouts />
      <div className="gp-resource-join gp-container"><Link className="gp-button" to="/register">Register your school</Link></div>
    </main>
    <PublicFooter />
  </div>
}
