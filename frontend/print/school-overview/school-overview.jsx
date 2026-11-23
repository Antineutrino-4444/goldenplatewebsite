import { useEffect } from 'react'
import { createRoot } from 'react-dom/client'
import { PlateMark } from '@/components/PublicHeader.jsx'
import '@/theme.css'
import '@/components/LandingPage.css'
import './school-overview.css'

const guideUrl = 'https://goldenplate.ca/getting-started'
const isDark = new URLSearchParams(window.location.search).get('theme') === 'dark'
document.documentElement.classList.toggle('dark', isDark)

export default function SchoolOverview() {
  useEffect(() => {
    const images = Array.from(document.images, image => image.decode())
    Promise.all([document.fonts.ready, ...images]).then(() => {
      document.documentElement.dataset.printReady = 'true'
    }).catch(error => console.error('Could not load the school overview for print.', error))
  }, [])

  return <main className="school-handout golden-public">
    <header className="handout-masthead">
      <a className="public-brand" href="https://goldenplate.ca">
        <PlateMark />
        <span>golden plate<span className="brand-caption">Student-Led Food Waste Prevention</span></span>
      </a>
      <span className="handout-edition">School Overview</span>
    </header>

    <section className="handout-intro">
      <h1>Bring Golden Plate to Your School</h1>
      <p>Students at St. Andrew’s College in Aurora, Ontario, started Golden Plate to reduce food waste in their dining hall. Your school can start with one lunch.</p>
    </section>

    <section className="handout-lunch" aria-labelledby="dish-return">
      <figure>
        <img src="/images/initiative/compost-coaches.webp" width="1600" height="1280" alt="Two students in green caps record a classmate’s plate at the dish return." />
        <figcaption>Compost Coaches on lunch duty at St. Andrew’s College.</figcaption>
      </figure>
      <div className="handout-lunch-copy">
        <h2 id="dish-return">At the Dish Return</h2>
        <p>Students choose a portion they think they can finish. At the dish return, student volunteers called Compost Coaches count clean plates and plates with leftovers.</p>
        <p>A coach scans a student card or looks up a name, then records the plate category on the website.</p>
        <p>At St. Andrew’s, a clean plate earns an entry in a weekly draw. The winner helps choose Friday’s lunch.</p>
      </div>
    </section>

    <section className="handout-plan" aria-labelledby="first-lunch">
      <h2 id="first-lunch">Plan Your First Lunch</h2>
      <div className="handout-plan-columns">
        <div>
          <h3>Gather Your Team</h3>
          <p>Bring together a staff mentor, student volunteers and someone from food services. Pick a lunch date and a reward that fits your school.</p>
        </div>
        <div>
          <h3>Record and Share</h3>
          <p>Once your school is approved, open a lunch session in the recorder. Share the clean-plate total at assembly and compare the counts from one lunch to the next.</p>
        </div>
      </div>
    </section>

    <footer className="handout-registration">
      <div>
        <h2>Register Your School</h2>
        <p>Choose one person to verify a contact email and request your school’s first administrator account. The Golden Plate team reviews the request.</p>
        <a className="handout-url" href={guideUrl}>goldenplate.ca/getting-started</a>
      </div>
      <a className="handout-qr" href={guideUrl}>
        <img src="./register-qr.svg" alt="Scan to open the Golden Plate getting-started guide." width="104" height="104" />
      </a>
    </footer>
  </main>
}

createRoot(document.getElementById('root')).render(<SchoolOverview />)
