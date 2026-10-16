import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { geoDistance, geoGraticule10, geoOrthographic, geoPath } from 'd3-geo'
import { hasGeographicCoordinates } from '@/lib/mapCoordinates.js'

const START = [65, -24, 0]

// Lightweight globe for the public landing page. The login flight uses Mapbox.
// Geographic pins come exclusively from the existing public school endpoint.
export default function SchoolGlobe({ schools = [], onSelect, paused = false }) {
  const [land, setLand] = useState(null)
  const [rotation, setRotation] = useState(START)
  const scale = 205
  const ref = useRef(null)
  const id = useId().replace(/:/g, '')
  useEffect(() => {
    const controller = new AbortController()
    fetch('/images/initiative/world-land.geojson', { signal: controller.signal })
      .then((r) => { if (!r.ok) throw new Error('No land data'); return r.json() }).then(setLand).catch(() => {})
    return () => controller.abort()
  }, [])
  useEffect(() => {
    if (paused || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    let timer
    const observer = new IntersectionObserver(([entry]) => {
      clearInterval(timer)
      if (entry.isIntersecting) timer = setInterval(() => {
        if (!document.hidden) setRotation((r) => [r[0] + 0.35, r[1], 0])
      }, 80)
    })
    if (ref.current) observer.observe(ref.current)
    return () => { clearInterval(timer); observer.disconnect() }
  }, [paused])
  const projection = geoOrthographic().translate([250, 250]).scale(scale).rotate(rotation).clipAngle(90)
  const path = geoPath(projection)
  const grid = useMemo(() => geoGraticule10(), [])
  const center = [-rotation[0], -rotation[1]]
  const pins = schools.filter(hasGeographicCoordinates).filter((s) => geoDistance([s.longitude, s.latitude], center) < Math.PI / 2)
  return <div ref={ref} className="school-globe">
    <svg viewBox="0 0 500 500" role="group" aria-label="Globe showing participating schools with saved public locations">
      <defs><radialGradient id={`${id}-ocean`} cx="34%" cy="28%" r="75%"><stop stopColor="#2c6657" /><stop offset="1" stopColor="#0b3027" /></radialGradient><clipPath id={`${id}-clip`}><circle cx="250" cy="250" r={scale} /></clipPath></defs>
      <circle cx="250" cy="250" r={Math.min(235, scale + 20)} fill="none" stroke="#8ea99b" strokeOpacity=".2" strokeDasharray="2 8" />
      <circle cx="250" cy="250" r={scale} fill={`url(#${id}-ocean)`} stroke="#809c85" strokeWidth="1" />
      <g clipPath={`url(#${id}-clip)`}>
        <path d={path(grid) || ''} fill="none" stroke="#b1c3a8" strokeWidth=".6" opacity=".2" />
        {land && <path d={path(land) || ''} fill="#8ea68a" stroke="#adc0a0" strokeWidth=".4" />}
        {pins.map((s) => {
          const [x, y] = projection([s.longitude, s.latitude])
          return <g key={s.id} transform={`translate(${x} ${y})`}>
            <circle r="8" fill="#f1c563" opacity=".22" />
            {onSelect ? <g role="button" tabIndex="0" aria-label={`View ${s.name}`} onClick={() => onSelect(s)} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(s) } }} className="globe-pin"><circle r="14" fill="transparent" /><circle r="4.5" fill="#f4cb6a" stroke="#fff5cf" strokeWidth="1.5" /><title>{s.name}</title></g> : <circle r="5" fill="#f4cb6a" stroke="#fff5cf" strokeWidth="1.5"><title>{s.name}</title></circle>}
          </g>
        })}
      </g>
    </svg>
  </div>
}
