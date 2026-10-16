import { useEffect, useMemo, useRef, useState } from 'react'
import { Map as VectorMap, Marker, Popup, NavigationControl } from 'mapbox-gl/esm'
import 'mapbox-gl/dist/mapbox-gl.css'
import { Globe2, Map as MapIcon, RotateCcw, LocateFixed, Layers3, Check, PersonStanding, ExternalLink, X } from 'lucide-react'
import './WorldMap.css'
import PlaceSearch from '@/components/PlaceSearch.jsx'
import EnglishScaleControl from '@/lib/EnglishScaleControl.js'
import { maxSchoolSessions, schoolActivity, schoolSessionLabel } from '@/lib/schoolMap.js'
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover.jsx'
import { hasGeographicCoordinates, wrapLongitude } from '@/lib/mapCoordinates.js'
import { MAP_VIEW_EVENT, MAP_VIEW_KEY, projectionFor, readMapView, schoolBounds } from '@/lib/mapView.js'
import { applyBasemap, BASEMAPS, isPublicMapboxToken, MAP_LANGUAGE, MAP_WORLDVIEW, mapStyleFor, MAP_LAYERS_EVENT, MAP_LAYERS_KEY, readMapLayers, streetViewUrl } from '@/lib/mapLayers.js'

const MAPBOX_TOKEN = (import.meta.env.VITE_MAPBOX_ACCESS_TOKEN || '').trim()
const MAP_CONFIGURED = isPublicMapboxToken(MAPBOX_TOKEN)
const EMPTY_PINS = []
const EMPTY_COUNTS = {}

function markerElement(name, selected = false, pending = false) {
  const element = document.createElement('button')
  element.type = 'button'
  element.className = `world-map-pin${selected ? ' is-selected' : ''}${pending ? ' is-pending' : ''}`
  element.title = name
  element.setAttribute('role', 'button')
  element.setAttribute('aria-label', name)
  element.innerHTML = '<span aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M12 21s7-6 7-12a7 7 0 1 0-14 0c0 6 7 12 7 12Z"/><circle cx="12" cy="9" r="2.5"/></svg></span>'
  return element
}

function popupContent(point) {
  const content = document.createElement('div')
  const name = document.createElement('strong')
  name.textContent = point.name || point.location_name || 'Selected location'
  const address = document.createElement('p')
  address.textContent = point.address || ''
  content.append(name, address)
  if (point.type === 'school') {
    const activity = document.createElement('p')
    activity.textContent = schoolSessionLabel(point.session_count)
    content.append(activity)
  }
  return content
}

export default function WorldMap({
  pins = EMPTY_PINS, submissionsByPin = EMPTY_COUNTS, selectedPinId = null, onSelectPin,
  pendingPoint = null, onMapClick, fillContainer = false, className = '',
  onPlaceSelect, initialSearchQuery = '', showSearch = true, compact = false, focusPoint = null,
}) {
  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const callbacks = useRef({ onMapClick, onSelectPin })
  const initialPoint = useRef(pendingPoint)
  const [view, setView] = useState(() => { try { return readMapView(window.localStorage) } catch { return 'globe' } })
  const viewRef = useRef(view)
  const [layers, setLayers] = useState(() => { try { return readMapLayers(window.localStorage) } catch { return readMapLayers() } })
  const layersRef = useRef(layers)
  const [layersOpen, setLayersOpen] = useState(false)
  const [streetViewPicking, setStreetViewPicking] = useState(false)
  const streetViewPickingRef = useRef(false)
  const [streetViewPoint, setStreetViewPoint] = useState(null)
  const [ready, setReady] = useState(false)
  const [loading, setLoading] = useState(true)
  const [mapError, setMapError] = useState(false)
  const [fatalError, setFatalError] = useState(false)
  const [generation, setGeneration] = useState(0)
  const [searchedPlace, setSearchedPlace] = useState(null)
  const geographicPins = useMemo(() => pins.filter(hasGeographicCoordinates), [pins])
  const mostSessions = useMemo(() => maxSchoolSessions(pins.filter((pin) => pin.type === 'school')), [pins])
  const selectedPoint = pendingPoint || focusPoint || searchedPlace || pins.find((pin) => pin.id === selectedPinId)
  const streetViewTarget = streetViewPoint || selectedPoint
  const streetViewLink = streetViewUrl(streetViewTarget)

  useEffect(() => { callbacks.current = { onMapClick, onSelectPin } }, [onMapClick, onSelectPin])
  useEffect(() => { viewRef.current = view }, [view])
  useEffect(() => { layersRef.current = layers }, [layers])
  useEffect(() => { streetViewPickingRef.current = streetViewPicking }, [streetViewPicking])
  useEffect(() => { setStreetViewPoint(null); if (selectedPinId) setSearchedPlace(null) }, [selectedPinId, pendingPoint, focusPoint])
  useEffect(() => {
    if (!streetViewPicking) return
    const cancel = (event) => { if (event.key === 'Escape') setStreetViewPicking(false) }
    window.addEventListener('keydown', cancel)
    return () => window.removeEventListener('keydown', cancel)
  }, [streetViewPicking])
  useEffect(() => {
    const sync = () => { try { setView(readMapView(window.localStorage)) } catch { /* Keep the current view if storage is unavailable. */ } }
    window.addEventListener('storage', sync)
    window.addEventListener(MAP_VIEW_EVENT, sync)
    return () => { window.removeEventListener('storage', sync); window.removeEventListener(MAP_VIEW_EVENT, sync) }
  }, [])
  useEffect(() => {
    const sync = () => {
      try {
        const { showSchools } = readMapLayers(window.localStorage)
        setLayers((current) => ({ ...current, showSchools }))
      } catch { /* Keep this map's choices. */ }
    }
    window.addEventListener('storage', sync)
    window.addEventListener(MAP_LAYERS_EVENT, sync)
    return () => { window.removeEventListener('storage', sync); window.removeEventListener(MAP_LAYERS_EVENT, sync) }
  }, [])

  useEffect(() => {
    setLoading(true)
    setReady(false)
    setFatalError(false)
    setMapError(false)
    if (!MAP_CONFIGURED) { setLoading(false); return }
    let map
    let resize
    try {
      const initial = initialPoint.current
      map = new VectorMap({
        container: containerRef.current, style: mapStyleFor(layersRef.current.basemap),
        accessToken: MAPBOX_TOKEN, worldview: MAP_WORLDVIEW, language: MAP_LANGUAGE,
        center: hasGeographicCoordinates(initial) ? [initial.longitude, initial.latitude] : [-35, 22],
        zoom: hasGeographicCoordinates(initial) ? 14 : 1.05,
        minZoom: 0, maxZoom: 22, maxPitch: 0,
        dragRotate: false, pitchWithRotate: false, touchPitch: false,
        antialias: true,
        attributionControl: { compact: true },
      })
      mapRef.current = map
      map.touchZoomRotate.disableRotation()
      map.addControl(new NavigationControl({ showCompass: false }), 'top-right')
      map.addControl(new EnglishScaleControl({ maxWidth: 100 }), 'bottom-left')
      map.on('style.load', () => {
        map.setWorldview(MAP_WORLDVIEW)
        map.setProjection(projectionFor(viewRef.current))
        map.setFog({ color: '#b5e0ed', 'high-color': '#183951', 'space-color': '#071b2c', 'star-intensity': 0.15 })
        applyBasemap(map, layersRef.current.basemap)
        setReady(true)
      })
      map.on('idle', () => setLoading(false))
      map.on('error', () => { setMapError(true); setLoading(false) })
      map.on('webglcontextlost', () => { setFatalError(true); setLoading(false) })
      map.on('webglcontextrestored', () => { setFatalError(false); map.triggerRepaint() })
      map.on('click', (event) => {
        // Ignore clicks in space outside the globe.
        const surfacePoint = map.project(event.lngLat)
        if (Math.hypot(surfacePoint.x - event.point.x, surfacePoint.y - event.point.y) > 4) return
        if (streetViewPickingRef.current) {
          setStreetViewPoint({ latitude: event.lngLat.lat, longitude: wrapLongitude(event.lngLat.lng), name: 'Selected spot' })
          setStreetViewPicking(false)
          return
        }
        if (callbacks.current.onMapClick) callbacks.current.onMapClick(event.lngLat.lat, wrapLongitude(event.lngLat.lng))
        else callbacks.current.onSelectPin?.(null)
      })
      resize = new ResizeObserver(() => map.resize())
      resize.observe(containerRef.current)
    } catch {
      setFatalError(true)
      setLoading(false)
    }
    return () => {
      resize?.disconnect()
      map?.remove()
      mapRef.current = null
    }
  }, [generation])

  useEffect(() => {
    if (ready) mapRef.current?.setProjection(projectionFor(view))
  }, [view, ready])

  useEffect(() => {
    if (ready) {
      setMapError(false)
      applyBasemap(mapRef.current, layers.basemap)
    }
  }, [layers.basemap, ready])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    const markers = []
    const popups = []
    for (const pin of layers.showSchools ? geographicPins : []) {
      const count = submissionsByPin[pin.id] || 0
      const isSchool = pin.type === 'school'
      const activity = schoolActivity(pin.session_count, mostSessions)
      const label = isSchool ? `${pin.name} · ${schoolSessionLabel(pin.session_count)}` : `${pin.name}${count ? ` (${count})` : ''}`
      const element = markerElement(label, pin.id === selectedPinId)
      if (isSchool) {
        element.classList.add('has-activity')
        element.style.setProperty('--pin-width', `${activity.width}px`)
        element.style.setProperty('--pin-height', `${activity.height}px`)
        element.style.setProperty('--pin-colour', `hsl(44 ${8 + 84 * activity.emphasis}% ${70 - 20 * activity.emphasis}%)`)
        element.style.setProperty('--pin-halo', `${activity.emphasis * 0.38}`)
        element.style.zIndex = pin.id === selectedPinId ? 101 : Math.round(activity.emphasis * 100)
      }
      element.addEventListener('click', (event) => { event.stopPropagation(); callbacks.current.onSelectPin?.(pin.id) })
      markers.push(new Marker({ element, anchor: 'bottom' }).setLngLat([pin.longitude, pin.latitude]).addTo(map))
      if (pin.id === selectedPinId) popups.push(new Popup({ offset: isSchool ? activity.height - 8 : 34, closeButton: false })
        .setLngLat([pin.longitude, pin.latitude]).setDOMContent(popupContent(pin)).addTo(map))
    }
    if (hasGeographicCoordinates(pendingPoint)) {
      const element = markerElement('Selected school location', false, true)
      element.addEventListener('click', (event) => event.stopPropagation())
      markers.push(new Marker({ element, anchor: 'bottom', draggable: true })
        .setLngLat([pendingPoint.longitude, pendingPoint.latitude]).addTo(map).on('dragend', (event) => {
          const location = event.target.getLngLat()
          callbacks.current.onMapClick?.(location.lat, wrapLongitude(location.lng))
        }))
    }
    if (hasGeographicCoordinates(searchedPlace)) {
      const element = markerElement(searchedPlace.name, false, true)
      element.addEventListener('click', (event) => event.stopPropagation())
      markers.push(new Marker({ element, anchor: 'bottom' }).setLngLat([searchedPlace.longitude, searchedPlace.latitude]).addTo(map))
      popups.push(new Popup({ offset: 34, closeButton: false }).setLngLat([searchedPlace.longitude, searchedPlace.latitude])
        .setDOMContent(popupContent(searchedPlace)).addTo(map))
    }
    if (hasGeographicCoordinates(streetViewPoint)) {
      const element = markerElement('Street View spot', false, true)
      element.addEventListener('click', (event) => event.stopPropagation())
      markers.push(new Marker({ element, anchor: 'bottom' }).setLngLat([streetViewPoint.longitude, streetViewPoint.latitude]).addTo(map))
    }
    return () => { markers.forEach((marker) => marker.remove()); popups.forEach((popup) => popup.remove()) }
  }, [geographicPins, mostSessions, submissionsByPin, selectedPinId, pendingPoint, searchedPlace, streetViewPoint, layers.showSchools, ready])

  useEffect(() => {
    const point = focusPoint || geographicPins.find((pin) => pin.id === selectedPinId)
    if (ready && hasGeographicCoordinates(point)) mapRef.current?.flyTo({ center: [point.longitude, point.latitude], zoom: focusPoint ? 16 : 15.5, duration: 950 })
  }, [focusPoint, selectedPinId, geographicPins, ready])

  const changeView = (next) => {
    setView(next)
    try {
      window.localStorage.setItem(MAP_VIEW_KEY, next)
      window.dispatchEvent(new Event(MAP_VIEW_EVENT))
    } catch { /* The selected view still works when storage is unavailable. */ }
  }
  const showWorld = () => mapRef.current?.flyTo({ center: [-35, 22], zoom: view === 'globe' ? 1.05 : 0, bearing: 0, pitch: 0, duration: 900 })
  const changeLayers = (updates) => {
    const next = { ...layers, ...updates }
    layersRef.current = next
    setLayers(next)
    try {
      window.localStorage.setItem(MAP_LAYERS_KEY, JSON.stringify({ showSchools: next.showSchools }))
      window.dispatchEvent(new Event(MAP_LAYERS_EVENT))
    } catch { /* Layer choices still work without storage. */ }
  }
  const pickStreetView = () => { setLayersOpen(false); setStreetViewPoint(null); setStreetViewPicking(true) }
  const showLocations = () => {
    const bounds = schoolBounds(geographicPins)
    if (bounds) mapRef.current?.fitBounds(bounds, { padding: 55, maxZoom: 13, duration: 900 })
  }
  const choosePlace = (place) => {
    setStreetViewPoint(null)
    setStreetViewPicking(false)
    if (!hasGeographicCoordinates(place)) { setSearchedPlace(null); onSelectPin?.(place.id); return }
    mapRef.current?.flyTo({ center: [place.longitude, place.latitude], zoom: 16, duration: 1100 })
    if (onMapClick) {
      setSearchedPlace(null)
      if (onPlaceSelect) onPlaceSelect(place)
      else onMapClick(place.latitude, place.longitude)
    } else if (place.school_id && onSelectPin) {
      setSearchedPlace(null)
      onSelectPin(place.id)
    } else {
      onSelectPin?.(null)
      setSearchedPlace(place)
    }
  }

  return (
    <div className={`world-map flex min-h-0 flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm ${fillContainer ? 'flex-1' : ''} ${className}`}>
      {showSearch && <PlaceSearch initialQuery={initialSearchQuery} onChoose={choosePlace} />}
      <div className="world-map-toolbar">
        <div className="world-map-modes" role="group" aria-label="Map display mode">
          <button type="button" aria-pressed={view === 'globe'} onClick={() => changeView('globe')}><Globe2 size={15} />Globe</button>
          <button type="button" aria-pressed={view === 'flat'} onClick={() => changeView('flat')}><MapIcon size={15} />Flat map</button>
        </div>
        <Popover open={layersOpen} onOpenChange={setLayersOpen}>
          <PopoverTrigger asChild><button type="button" className="world-map-control" aria-label="Map layers"><Layers3 size={15} />Layers<span className="world-map-layer-name"> · {BASEMAPS.find(({ id }) => id === layers.basemap)?.name}</span></button></PopoverTrigger>
          <PopoverContent align="start" collisionPadding={12} sideOffset={8}
            style={{ maxHeight: 'var(--radix-popover-content-available-height)', overflowY: 'auto' }}
            className="world-map-layer-panel w-[290px] max-w-[calc(100vw-32px)] rounded-xl p-3" aria-label="Map layers">
            <h3 className="mb-2 px-1 text-sm font-semibold text-slate-800">Map layers</h3>
            <div role="radiogroup" aria-label="Base map" className="space-y-1">
              {BASEMAPS.map((basemap) => <label key={basemap.id} className={`world-map-layer-option ${layers.basemap === basemap.id ? 'is-active' : ''}`}>
                <input type="radio" name={`basemap-${compact ? 'picker' : 'explore'}`} value={basemap.id} checked={layers.basemap === basemap.id} onChange={() => changeLayers({ basemap: basemap.id })} className="sr-only" />
                <span aria-hidden="true" className={`world-map-layer-swatch is-${basemap.id}`} />
                <span className="flex-1"><span className="block text-xs font-semibold">{basemap.name}</span><span className="block text-[10px] text-slate-500">{basemap.description}</span></span>
                {layers.basemap === basemap.id && <Check size={15} className="text-teal-700" />}
              </label>)}
            </div>
            <div className="my-3 border-t border-slate-100" />
            <label className="flex cursor-pointer items-center justify-between gap-3 px-1 text-xs text-slate-700"><span>School pins</span><input type="checkbox" checked={layers.showSchools} onChange={(event) => changeLayers({ showSchools: event.target.checked })} className="accent-teal-700" /></label>
            <div className="my-3 border-t border-slate-100" />
            <div className="px-1">
              <p className="flex items-center gap-1.5 text-xs font-semibold text-slate-700"><PersonStanding size={15} />Street View</p>
              <p className="mb-2 mt-1 text-[11px] leading-4 text-slate-500">Explore nearby panoramas in Google Maps. Coverage varies by location.</p>
              {streetViewLink && <a href={streetViewLink} target="_blank" rel="noopener noreferrer" className="mb-2 flex items-center gap-1 text-xs font-semibold text-teal-700">Open Street View<ExternalLink size={12} /></a>}
              <button type="button" className="world-map-control w-full" onClick={pickStreetView} disabled={!ready}>Choose a spot on the map</button>
            </div>
          </PopoverContent>
        </Popover>
        <div className="ml-auto flex flex-wrap gap-1">
          <button type="button" className="world-map-control" onClick={showWorld} disabled={!ready}><RotateCcw size={14} />Reset view</button>
          {geographicPins.length > 0 && <button type="button" className="world-map-control" onClick={showLocations} disabled={!ready}><LocateFixed size={14} />Show schools</button>}
          {searchedPlace && <button type="button" className="world-map-control" onClick={() => setSearchedPlace(null)}>Clear preview</button>}
        </div>
      </div>
      <div className={`relative isolate min-h-0 ${fillContainer ? 'flex-1' : compact ? 'h-[260px] sm:h-[320px]' : 'h-[420px] sm:h-[540px]'}`}>
        <div ref={containerRef} role="region" aria-label={onMapClick ? 'Interactive school location picker' : 'Interactive school map'}
          className={`world-map-canvas absolute inset-0 ${onMapClick || streetViewPicking ? 'world-map-placement' : ''}`} />
        {(streetViewPicking || streetViewPoint) && <div className="world-map-street-view absolute left-3 right-14 top-3 z-10 max-w-xs rounded-xl border border-slate-200 bg-white p-3 shadow-lg">
          <div className="flex items-start gap-2"><PersonStanding size={18} className="shrink-0 text-teal-700" /><div className="flex-1">
            <p className="text-xs font-semibold text-slate-800">{streetViewPicking ? 'Choose a Street View spot' : 'Street View at this spot'}</p>
            {streetViewPicking ? <p role="status" className="mt-1 text-[11px] text-slate-500">Zoom in, then click a road or place on the map.</p> : <a href={streetViewLink} target="_blank" rel="noopener noreferrer" className="mt-1 flex items-center gap-1 text-xs font-semibold text-teal-700">Open in Google Maps<ExternalLink size={12} /></a>}
          </div><button type="button" aria-label="Close Street View selection" onClick={() => { setStreetViewPicking(false); setStreetViewPoint(null) }} className="text-slate-400 hover:text-slate-700"><X size={15} /></button></div>
        </div>}
        {!MAP_CONFIGURED && <div role="status" className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-slate-950/95 p-6 text-center text-sm text-white">
          <Globe2 size={30} /><p>The map is being set up.</p><p className="max-w-xs text-xs text-slate-300">You can still search participating schools and view their details.</p>
        </div>}
        {MAP_CONFIGURED && loading && !fatalError && !streetViewPicking && !streetViewPoint && <div role="status" className="pointer-events-none absolute left-3 top-3 rounded-full bg-white/95 px-3 py-1.5 text-xs text-slate-600 shadow">Loading map…</div>}
        {fatalError && <div role="alert" className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-slate-950/95 p-6 text-center text-sm text-white">
          <Globe2 size={30} /><p>The map could not start. Check that hardware graphics are enabled in your browser.</p>
          <button className="world-map-control" type="button" onClick={() => setGeneration((current) => current + 1)}>Retry map</button>
        </div>}
      </div>
      {geographicPins.some((pin) => pin.type === 'school') && <div className="flex shrink-0 flex-wrap items-center gap-x-3 gap-y-1 border-t border-slate-100 px-3 py-2 text-[11px] text-slate-500" aria-label="School activity legend">
        <span className="inline-flex items-center gap-2"><span aria-hidden="true" className="world-map-activity-key" />More public sessions → bigger, golder pins</span>
        <span>Relative to all schools · Teal outline = selected</span>
      </div>}
      {mapError && !fatalError && <div role="status" className="flex items-center gap-3 bg-amber-50 px-3 py-2 text-xs text-amber-950">
        <span>The map service could not load some detail. Please try again later.</span>
        <button type="button" className="world-map-control shrink-0" onClick={() => setGeneration((current) => current + 1)}>Retry map</button>
      </div>}
      <div className="flex shrink-0 flex-wrap items-center gap-2 border-t border-slate-100 px-3 py-2 text-xs text-slate-500">
        <span className="mr-auto">Drag to explore · Scroll or pinch to zoom{onMapClick ? ' · Click to place, drag pin to adjust' : ''}</span>
        {onSelectPin && geographicPins.length > 0 && <select aria-label="Choose a school on the map" className="max-w-full rounded border bg-white px-2 py-1 text-slate-700"
          value={geographicPins.some((pin) => pin.id === selectedPinId) ? selectedPinId : ''}
          onChange={(event) => onSelectPin(event.target.value || null)}>
          <option value="">Choose a school…</option>
          {geographicPins.map((pin) => <option key={pin.id} value={pin.id}>{pin.code ? `${pin.code} · ` : ''}{pin.name}</option>)}
        </select>}
      </div>
    </div>
  )
}
