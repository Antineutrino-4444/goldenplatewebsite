import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { ArrowRight } from 'lucide-react'
import { hasGeographicCoordinates } from '@/lib/mapCoordinates.js'
import { schoolFlightDeadline } from '@/lib/school-flight.js'
import './LandingPage.css'

function UnavailableFlight({ onComplete }) {
  useEffect(onComplete, [onComplete])
  return null
}
const SchoolFlightMap = lazy(() => import('@/components/SchoolFlightMap.jsx').catch((error) => {
  console.warn('Unable to load the school globe animation:', error)
  return { default: UnavailableFlight }
}))

export default function SchoolArrival({ user, onComplete }) {
  const [flight, setFlight] = useState(null)
  const [phase, setPhase] = useState('loading')
  const overlay = useRef(null)
  const deadline = useRef(null)
  const complete = useRef(onComplete)
  useEffect(() => { complete.current = onComplete }, [onComplete])
  const finish = useCallback(() => complete.current(), [])
  const schoolId = user?.school?.id
  useEffect(() => {
    const controller = new AbortController()
    // Always keep an independent exit: network or rendering cannot block login.
    deadline.current = schoolFlightDeadline(finish)
    const escape = (e) => { if (e.key === 'Escape') finish() }
    const motion = window.matchMedia('(prefers-reduced-motion: reduce)')
    const motionChanged = () => { if (motion.matches) finish() }
    const hidden = () => { if (document.hidden) finish() }
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    window.addEventListener('keydown', escape)
    document.addEventListener('visibilitychange', hidden)
    motion.addEventListener('change', motionChanged)
    const schools = fetch('/api/map/schools', { signal: controller.signal }).then((r) => {
      if (!r.ok) throw new Error('Schools unavailable')
      return r.json()
    })
    schools.then((data) => {
      if (controller.signal.aborted) return
      const list = Array.isArray(data.schools) ? data.schools : []
      const destination = list.find((s) => s.school_id === schoolId)
      if (!hasGeographicCoordinates(destination)) {
        console.info('School globe skipped: this school has no published map location.')
        finish(); return
      }
      setFlight({ schools: list, destination })
    }).catch((error) => {
      if (error.name !== 'AbortError') {
        console.warn('Unable to prepare the school globe animation:', error)
        finish()
      }
    })
    return () => {
      controller.abort(); deadline.current?.dispose()
      window.removeEventListener('keydown', escape)
      document.removeEventListener('visibilitychange', hidden)
      motion.removeEventListener('change', motionChanged)
      document.body.style.overflow = previousOverflow
    }
  }, [schoolId, finish])
  const progress = useCallback((opacity, nextPhase) => {
    deadline.current?.ready()
    if (overlay.current) overlay.current.style.opacity = opacity
    if (nextPhase) setPhase(nextPhase)
  }, [])
  const keepFocus = (event) => {
    if (event.key !== 'Tab') return
    const controls = [...overlay.current.querySelectorAll('a[href], button, summary, [tabindex="0"]')].filter((element) => !element.disabled && element.offsetParent !== null)
    const first = controls[0], last = controls.at(-1)
    if (event.shiftKey && (document.activeElement === first || !overlay.current.contains(document.activeElement))) { event.preventDefault(); last?.focus() }
    else if (!event.shiftKey && (document.activeElement === last || !overlay.current.contains(document.activeElement))) { event.preventDefault(); first?.focus() }
  }
  return <section ref={overlay} className="school-arrival" role="dialog" aria-modal="true" aria-labelledby="arrival-title" data-phase={phase} onKeyDown={keepFocus}>
    {flight && <Suspense fallback={null}><SchoolFlightMap {...flight} onProgress={progress} onComplete={finish} /></Suspense>}
    <header className="arrival-heading"><p>Golden Plate</p><h1 id="arrival-title">Welcome to {user?.school?.name || 'your school'}.</h1></header>
    <div className="arrival-controls"><p role="status">{phase === 'loading' ? 'Opening your school’s globe…' : phase === 'zoom' ? 'Opening your recording page…' : 'On our way to your school.'}</p>
      <button autoFocus className="gp-button" onClick={finish}>Continue to portal <ArrowRight size={17} /></button>
    </div>
  </section>
}
