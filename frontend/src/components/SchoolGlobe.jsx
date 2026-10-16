import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { geoDistance, geoGraticule10, geoOrthographic, geoPath } from 'd3-geo'
import { hasGeographicCoordinates } from '@/lib/mapCoordinates.js'
import { GLOBE_ORIGIN } from '@/lib/globe-origin.js'
import { startGlobeAnimation } from '@/lib/globe-animation.js'

const START = [-GLOBE_ORIGIN.longitude, -GLOBE_ORIGIN.latitude, 0]

// Lightweight globe for the public landing page. The login flight uses Mapbox.
// Geographic pins come exclusively from the existing public school endpoint.
export default function SchoolGlobe({ schools = [], onSelect, paused = false }) {
  const [land, setLand] = useState(null)
  const rotation = useRef([...START])
  const scale = 205
  const ref = useRef(null)
  const gridRef = useRef(null)
  const landRef = useRef(null)
  const pinRefs = useRef(new Map())
  const projection = useMemo(() => geoOrthographic().translate([250, 250]).scale(205).clipAngle(90), [])
  const path = useMemo(() => geoPath(projection), [projection])
  const grid = useMemo(() => geoGraticule10(), [])
  const mappedSchools = useMemo(() => schools.filter(hasGeographicCoordinates), [schools])
  const id = useId().replace(/:/g, '')
  useEffect(() => {
    const controller = new AbortController()
    fetch('/images/initiative/world-land.geojson', { signal: controller.signal })
      .then((r) => { if (!r.ok) throw new Error('No land data'); return r.json() }).then(setLand).catch(() => {})
    return () => controller.abort()
  }, [])
  useEffect(() => {
    const draw = () => {
      projection.rotate(rotation.current)
      gridRef.current?.setAttribute('d', path(grid) || '')
      landRef.current?.setAttribute('d', land ? path(land) || '' : '')
      const center = [-rotation.current[0], -rotation.current[1]]
      for (const school of mappedSchools) {
        const node = pinRefs.current.get(school.id)
        if (!node) continue
        const visible = geoDistance([school.longitude, school.latitude], center) < Math.PI / 2
        node.setAttribute('visibility', visible ? 'visible' : 'hidden')
        if (visible) {
          const [x, y] = projection([school.longitude, school.latitude])
          node.setAttribute('transform', `translate(${x} ${y})`)
        }
      }
    }
    draw()
    if (paused) return
    // Updating the two paths and existing pin nodes avoids reconciling the
    // entire SVG through React on every animation frame.
    return startGlobeAnimation(ref.current, (degrees) => {
      rotation.current[0] = (rotation.current[0] + degrees) % 360
      draw()
    })
  }, [paused, land, mappedSchools, grid, path, projection])
  projection.rotate(rotation.current)
  const center = [-rotation.current[0], -rotation.current[1]]
  return <div ref={ref} className="school-globe">
    <svg viewBox="0 0 500 500" role="group" aria-label="Globe showing participating schools with saved public locations">
      <defs><radialGradient id={`${id}-ocean`} cx="34%" cy="28%" r="75%"><stop stopColor="#2c6657" /><stop offset="1" stopColor="#0b3027" /></radialGradient><clipPath id={`${id}-clip`}><circle cx="250" cy="250" r={scale} /></clipPath></defs>
      <circle cx="250" cy="250" r={Math.min(235, scale + 20)} fill="none" stroke="#8ea99b" strokeOpacity=".2" strokeDasharray="2 8" />
      <circle cx="250" cy="250" r={scale} fill={`url(#${id}-ocean)`} stroke="#809c85" strokeWidth="1" />
      <g clipPath={`url(#${id}-clip)`}>
        <path ref={gridRef} d={path(grid) || ''} fill="none" stroke="#b1c3a8" strokeWidth=".6" opacity=".2" />
        {land && <path ref={landRef} d={path(land) || ''} fill="#8ea68a" stroke="#adc0a0" strokeWidth=".4" />}
        {mappedSchools.map((s) => {
          const [x, y] = projection([s.longitude, s.latitude])
          const visible = geoDistance([s.longitude, s.latitude], center) < Math.PI / 2
          return <g key={s.id} ref={(node) => { if (node) pinRefs.current.set(s.id, node); else pinRefs.current.delete(s.id) }}
            visibility={visible ? 'visible' : 'hidden'} transform={`translate(${x} ${y})`}>
            <circle r="8" fill="#f1c563" opacity=".22" />
            {onSelect ? <g role="button" tabIndex="0" aria-label={`View ${s.name}`} onClick={() => onSelect(s)} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(s) } }} className="globe-pin"><circle r="14" fill="transparent" /><circle r="4.5" fill="#f4cb6a" stroke="#fff5cf" strokeWidth="1.5" /><title>{s.name}</title></g> : <circle r="5" fill="#f4cb6a" stroke="#fff5cf" strokeWidth="1.5"><title>{s.name}</title></circle>}
          </g>
        })}
      </g>
    </svg>
  </div>
}
