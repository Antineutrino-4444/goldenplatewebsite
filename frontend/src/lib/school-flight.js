import { geoInterpolate } from 'd3-geo'
import { hasGeographicCoordinates } from './mapCoordinates.js'

export const DEFAULT_FLIGHT_ORIGIN = { longitude: -35, latitude: 22 }
export const FLIGHT_TURN_MS = 2800
export const FLIGHT_ZOOM_MS = 2400
export const FLIGHT_SETTLE_MS = 300
export const FLIGHT_DURATION_MS = FLIGHT_SETTLE_MS + FLIGHT_TURN_MS + FLIGHT_ZOOM_MS
const clamp = (value) => Math.max(0, Math.min(1, value))

// Loading a cold Mapbox module/style must not consume the camera's playback
// budget. Both stages still have independent exits so login cannot get stuck.
export function schoolFlightDeadline(onComplete, { setTimer = setTimeout, clearTimer = clearTimeout } = {}) {
  let playing = false
  let disposed = false
  let timer = setTimer(() => { if (!disposed) onComplete() }, 12000)
  return {
    ready() {
      if (playing || disposed) return
      playing = true
      clearTimer(timer)
      timer = setTimer(() => { if (!disposed) onComplete() }, FLIGHT_DURATION_MS + 3000)
    },
    dispose() { disposed = true; clearTimer(timer) },
  }
}

// Zero velocity and acceleration at both ends of the turn.
export function flightTurnProgress(value) {
  const t = clamp(value)
  return t * t * t * (t * (t * 6 - 15) + 10)
}

export function fullGlobeZoom(width, height) {
  // Mapbox's globe circumference is 512 * 2^zoom pixels. Leave space around
  // the whole hemisphere on narrow phones as well as wide desktop screens.
  return Math.max(-2.5, Math.min(2.25, Math.log2(Math.max(1, Math.min(width, height)) * 0.66 * Math.PI / 512)))
}

export function createSchoolFlight(origin, destination) {
  const from = hasGeographicCoordinates(origin) ? origin : DEFAULT_FLIGHT_ORIGIN
  const route = geoInterpolate([from.longitude, from.latitude], [destination.longitude, destination.latitude])
  return (elapsed, worldZoom) => {
    const turn = flightTurnProgress((elapsed - FLIGHT_SETTLE_MS) / FLIGHT_TURN_MS)
    const zoom = clamp((elapsed - FLIGHT_SETTLE_MS - FLIGHT_TURN_MS) / FLIGHT_ZOOM_MS)
    return {
      center: route(turn),
      // Quadratic progress gives the zoom constant acceleration from rest.
      zoom: worldZoom + (13 - worldZoom) * zoom * zoom,
      opacity: 1 - flightTurnProgress((zoom - 0.72) / 0.28),
      phase: elapsed < FLIGHT_SETTLE_MS ? 'ready' : zoom > 0 ? 'zoom' : 'turn',
      complete: elapsed >= FLIGHT_DURATION_MS,
    }
  }
}

// City-level IP orientation only; never request GPS, send account details, or
// persist the visitor's coordinates. A failed lookup uses the normal world view.
let approximateOrigin
export async function lookupFlightOrigin({ signal, fetchImpl = fetch, timeoutMs = 1200 } = {}) {
  if (approximateOrigin) return approximateOrigin
  const controller = new AbortController()
  const abort = () => controller.abort()
  signal?.addEventListener('abort', abort, { once: true })
  if (signal?.aborted) controller.abort()
  const timeout = setTimeout(abort, timeoutMs)
  try {
    const response = await fetchImpl('https://ipwho.is/?fields=success,latitude,longitude', {
      signal: controller.signal, credentials: 'omit', referrerPolicy: 'no-referrer',
    })
    if (!response.ok) return DEFAULT_FLIGHT_ORIGIN
    const point = await response.json()
    if (point.success !== true || !hasGeographicCoordinates(point)) return DEFAULT_FLIGHT_ORIGIN
    return (approximateOrigin = { longitude: Math.round(point.longitude * 10) / 10, latitude: Math.round(point.latitude * 10) / 10 })
  } catch { return DEFAULT_FLIGHT_ORIGIN }
  finally { clearTimeout(timeout); signal?.removeEventListener('abort', abort) }
}
