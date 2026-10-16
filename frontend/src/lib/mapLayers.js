import { hasGeographicCoordinates } from './mapCoordinates.js'

export const MAP_LAYERS_KEY = 'goldenplate.map-layers.v1'
export const MAP_LAYERS_EVENT = 'goldenplate-map-layers-changed'
export const BASEMAPS = [
  { id: 'street', name: 'Street map', description: 'Clear roads and places' },
  { id: 'satellite', name: 'Satellite', description: 'Imagery with place names and boundaries' },
  { id: 'hybrid', name: 'Hybrid', description: 'Imagery with roads and labels' },
]
export const MAP_WORLDVIEW = 'CN'
// Label language is independent of territorial worldview. Use English globally;
// Mapbox falls back to the place's native name when no English name exists.
export const MAP_LANGUAGE = 'en'
export const STREET_STYLE = 'mapbox://styles/mapbox/standard'
export const SATELLITE_STYLE = 'mapbox://styles/mapbox/standard-satellite'

export function isPublicMapboxToken(value) {
  return typeof value === 'string' && /^pk\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/.test(value.trim())
}

export function readMapLayers(storage) {
  try {
    const value = JSON.parse(storage?.getItem(MAP_LAYERS_KEY) || 'null')
    // Every newly opened map starts in Hybrid, regardless of older saved choices.
    return { basemap: 'hybrid', showSchools: value?.showSchools !== false }
  } catch { return { basemap: 'hybrid', showSchools: true } }
}

export function mapStyleFor(basemap) {
  const street = basemap === 'street'
  const roads = basemap !== 'satellite'
  // Use Standard imports rather than rewriting its internal boundary filters.
  // Even the quieter Satellite mode retains territorial lines and place names.
  const config = {
    lightPreset: 'day', showPlaceLabels: true, showAdminBoundaries: true,
    showPointOfInterestLabels: roads, showRoadLabels: roads, showTransitLabels: roads,
    ...(street ? { show3dObjects: false } : { showRoadsAndTransit: roads, showPedestrianRoads: roads }),
  }
  return { version: 8, sources: {}, layers: [],
    imports: [{ id: 'basemap', url: street ? STREET_STYLE : SATELLITE_STYLE, config }] }
}

export function applyBasemap(map, basemap) {
  const style = mapStyleFor(basemap)
  const next = style.imports[0]
  const current = map.getStyle()?.imports?.find(({ id }) => id === 'basemap')
  if (current?.url === next.url) {
    map.setConfig('basemap', next.config)
  } else {
    // Retain the Map instance, camera, DOM school markers and map-load session.
    // Defer the explicit projection until style.load, when imports are ready.
    // Otherwise Mapbox can merge globe terrain before a fragment has loaded.
    map.setProjection(null)
    map.setStyle(style, { diff: false })
  }
}

export function streetViewUrl(point) {
  if (!hasGeographicCoordinates(point)) return null
  const parameters = new URLSearchParams({ api: '1', map_action: 'pano', viewpoint: `${point.latitude},${point.longitude}`, hl: 'en' })
  return `https://www.google.com/maps/@?${parameters}`
}
