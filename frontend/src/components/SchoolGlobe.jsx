import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { geoDistance, geoGraticule10, geoOrthographic, geoPath } from 'd3-geo'
import { Pause, Play } from 'lucide-react'
import { hasGeographicCoordinates, wrapLongitude } from '@/lib/mapCoordinates.js'
import { GLOBE_ORIGIN } from '@/lib/globe-origin.js'
import { startGlobeAnimation } from '@/lib/globe-animation.js'
import { connectGlobeDragging } from '@/lib/globe-drag.js'
import './SchoolGlobe.css'

const START = [-GLOBE_ORIGIN.longitude, -GLOBE_ORIGIN.latitude, 0]
const RADIUS = 205
const VIEW_SIZE = 500
const REDUCED_MOTION = '(prefers-reduced-motion: reduce)'
const KEY_MOVES = { ArrowLeft: [-10, 0], ArrowRight: [10, 0], ArrowUp: [0, 10], ArrowDown: [0, -10] }

export default function SchoolGlobe({ schools = [], onSelect }) {
  const [land, setLand] = useState(null)
  const [paused, setPaused] = useState(() => Boolean(globalThis.matchMedia?.(REDUCED_MOTION).matches))
  const [speed, setSpeed] = useState(1)
  const rotation = useRef([...START])
  const svgRef = useRef(null)
  const gridRef = useRef(null)
  const landRef = useRef(null)
  const pinRefs = useRef(new Map())
  const redraw = useRef(null)
  const projection = useMemo(() => geoOrthographic().translate([VIEW_SIZE / 2, VIEW_SIZE / 2]).scale(RADIUS).clipAngle(90), [])
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

  useLayoutEffect(() => {
    // Both dragging and animation update the same projection and existing SVG nodes.
    redraw.current = () => {
      projection.rotate(rotation.current)
      gridRef.current.setAttribute('d', path(grid) || '')
      landRef.current.setAttribute('d', land ? path(land) || '' : '')
      const center = [-rotation.current[0], -rotation.current[1]]
      for (const school of mappedSchools) {
        const node = pinRefs.current.get(school.id)
        if (!node) continue
        const coords = [school.longitude, school.latitude]
        const visible = geoDistance(coords, center) < Math.PI / 2
        node.setAttribute('visibility', visible ? 'visible' : 'hidden')
        if (visible) {
          const [x, y] = projection(coords)
          node.setAttribute('transform', `translate(${x} ${y})`)
        }
      }
    }
    redraw.current()
    return () => { redraw.current = null }
  }, [land, mappedSchools, grid, path, projection])

  function pan(longitude, latitude) {
    setPaused(true)
    rotation.current[0] = wrapLongitude(rotation.current[0] + longitude)
    rotation.current[1] = Math.max(-90, Math.min(90, rotation.current[1] + latitude))
    redraw.current?.()
  }

  useEffect(() => {
    const svg = svgRef.current
    return connectGlobeDragging(svg, (dx, dy) => {
      const radiusPixels = svg.getBoundingClientRect().width * RADIUS / VIEW_SIZE
      if (radiusPixels) pan(dx * 180 / Math.PI / radiusPixels, -dy * 180 / Math.PI / radiusPixels)
    })
  }, [])

  useEffect(() => {
    const preference = globalThis.matchMedia?.(REDUCED_MOTION)
    const update = () => { if (preference.matches) setPaused(true) }
    preference?.addEventListener('change', update)
    return () => preference?.removeEventListener('change', update)
  }, [])

  useEffect(() => {
    if (paused) return
    return startGlobeAnimation(svgRef.current, (degrees) => {
      rotation.current[0] = wrapLongitude(rotation.current[0] + degrees * speed)
      redraw.current?.()
    }, { motion: null }) // Reduced motion starts paused; people can explicitly choose Play.
  }, [paused, speed])

  function keyPan(event) {
    const direction = KEY_MOVES[event.key]
    if (!direction || event.target !== event.currentTarget || event.ctrlKey || event.altKey || event.metaKey) return
    event.preventDefault()
    pan(...direction)
  }

  function selectSchool(school) {
    setPaused(true)
    onSelect(school)
  }

  return <>
    <div className="school-globe">
      <svg ref={svgRef} viewBox="0 0 500 500" role="group" tabIndex="0"
        aria-label="School globe. Drag or use the arrow keys to rotate." onKeyDown={keyPan}>
        <defs><radialGradient id={`${id}-ocean`} cx="34%" cy="28%" r="75%"><stop stopColor="#2c6657" /><stop offset="1" stopColor="#0b3027" /></radialGradient><clipPath id={`${id}-clip`}><circle cx="250" cy="250" r={RADIUS} /></clipPath></defs>
        <circle cx="250" cy="250" r={RADIUS + 20} fill="none" stroke="#8ea99b" strokeOpacity=".2" strokeDasharray="2 8" />
        <circle className="globe-ocean" cx="250" cy="250" r={RADIUS} fill={`url(#${id}-ocean)`} stroke="#809c85" strokeWidth="1" />
        <g clipPath={`url(#${id}-clip)`}>
          <path ref={gridRef} fill="none" stroke="#b1c3a8" strokeWidth=".6" opacity=".2" />
          <path ref={landRef} fill="#8ea68a" stroke="#adc0a0" strokeWidth=".4" />
          {mappedSchools.map((school) => (
            <g key={school.id} ref={(node) => { if (node) pinRefs.current.set(school.id, node); else pinRefs.current.delete(school.id) }}>
              <circle r="8" fill="#f1c563" opacity=".22" />
              {onSelect ? <g role="button" tabIndex="0" aria-label={`View ${school.name}`} className="globe-pin"
                onFocus={() => setPaused(true)} onClick={() => selectSchool(school)} onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); selectSchool(school) }
                }}>
                <circle r="18" fill="transparent" /><circle r="4.5" fill="#f4cb6a" stroke="#fff5cf" strokeWidth="1.5" />
                <title>{school.name}</title>
              </g> : <circle r="5" fill="#f4cb6a" stroke="#fff5cf" strokeWidth="1.5"><title>{school.name}</title></circle>}
            </g>
          ))}
        </g>
      </svg>
    </div>
    <div className="gp-globe-controls" role="group" aria-label="Globe rotation">
      <button type="button" onClick={() => setPaused(!paused)} aria-label={paused ? 'Play globe rotation' : 'Pause globe rotation'}>
        {paused ? <Play size={15} aria-hidden="true" /> : <Pause size={15} aria-hidden="true" />}
        {paused ? 'Play' : 'Pause'}
      </button>
      <label>Speed
        <select value={speed} onChange={(event) => setSpeed(Number(event.target.value))} aria-label="Globe rotation speed">
          {[0.5, 1, 2, 4].map((rate) => <option key={rate} value={rate}>{rate}×</option>)}
        </select>
      </label>
    </div>
  </>
}
