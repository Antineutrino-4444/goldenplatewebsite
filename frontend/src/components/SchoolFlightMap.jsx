import { useEffect, useRef } from 'react'
import { Map as VectorMap, Marker } from 'mapbox-gl/esm'
import 'mapbox-gl/dist/mapbox-gl.css'
import { hasGeographicCoordinates } from '@/lib/mapCoordinates.js'
import { isPublicMapboxToken, MAP_LANGUAGE, MAP_WORLDVIEW, mapStyleFor } from '@/lib/mapLayers.js'
import { createSchoolFlight, fullGlobeZoom } from '@/lib/school-flight.js'

const token = (import.meta.env.VITE_MAPBOX_ACCESS_TOKEN || '').trim()

export default function SchoolFlightMap({ schools, destination, onProgress, onComplete }) {
  const container = useRef(null)
  const callbacks = useRef({ onProgress, onComplete })
  useEffect(() => { callbacks.current = { onProgress, onComplete } }, [onProgress, onComplete])
  useEffect(() => {
    if (!isPublicMapboxToken(token)) { callbacks.current.onComplete(); return }
    let map, frame, resize, started, lastPhase
    let finished = false
    const markers = []
    const finish = () => {
      if (finished) return
      finished = true
      cancelAnimationFrame(frame)
      callbacks.current.onComplete()
    }
    const camera = createSchoolFlight(destination)
    const animate = (now) => {
      if (finished) return
      started ??= now
      const bounds = container.current.getBoundingClientRect()
      const position = camera(now - started, fullGlobeZoom(bounds.width, bounds.height))
      map.jumpTo({ center: position.center, zoom: position.zoom, bearing: 0, pitch: 0 })
      callbacks.current.onProgress(position.opacity, position.phase !== lastPhase ? position.phase : null)
      lastPhase = position.phase
      if (position.complete) finish()
      else frame = requestAnimationFrame(animate)
    }
    try {
      const bounds = container.current.getBoundingClientRect()
      const initial = camera(0, fullGlobeZoom(bounds.width, bounds.height))
      map = new VectorMap({
        container: container.current, accessToken: token,
        // Standard imports must finish loading before enabling globe terrain.
        style: mapStyleFor('hybrid'),
        worldview: MAP_WORLDVIEW, language: MAP_LANGUAGE,
        center: initial.center, zoom: initial.zoom,
        minZoom: -2.5, maxZoom: 14, maxPitch: 0, interactive: false,
        antialias: true, attributionControl: { compact: true },
      })
      map.on('style.load', () => {
        map.setWorldview(MAP_WORLDVIEW)
        map.setLanguage(MAP_LANGUAGE)
        map.setProjection('globe')
        map.setFog({ color: '#b5e0ed', 'high-color': '#183951', 'space-color': '#071b2c', 'star-intensity': 0.15 })
      })
      map.once('load', () => {
        if (finished) return
        for (const school of schools.filter(hasGeographicCoordinates)) {
          const element = document.createElement('span')
          element.className = `arrival-school-pin${school.school_id === destination.school_id ? ' is-destination' : ''}`
          element.title = school.name
          element.setAttribute('aria-label', school.name)
          markers.push(new Marker({ element }).setLngLat([school.longitude, school.latitude]).addTo(map))
        }
        frame = requestAnimationFrame(animate)
      })
      map.on('webglcontextlost', finish)
      resize = new ResizeObserver(() => map.resize())
      resize.observe(container.current)
    } catch (error) {
      console.warn('Unable to start the school globe animation:', error)
      finish()
    }
    return () => {
      finished = true
      cancelAnimationFrame(frame)
      resize?.disconnect()
      markers.forEach((marker) => marker.remove())
      map?.remove()
    }
  }, [schools, destination])
  return <div ref={container} className="arrival-map" role="img" aria-label={`Satellite globe flying from Jiamusi to ${destination.name}`} />
}
