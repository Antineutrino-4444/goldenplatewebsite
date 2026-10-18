import { geoInterpolate } from 'd3-geo'
import { GLOBE_ORIGIN } from './globe-origin.js'

export const FLIGHT_TURN_MS = 1600
export const FLIGHT_ZOOM_MS = 650
export const FLIGHT_SETTLE_MS = 150
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

function smootherstep(value) {
  const t = clamp(value)
  return t * t * t * (t * (t * 6 - 15) + 10)
}

// Two passes give the turn a much stronger surge and slowdown while keeping
// velocity and acceleration continuous, including at the midpoint and ends.
export function flightTurnProgress(value) {
  return smootherstep(smootherstep(value))
}

export function fullGlobeZoom(width, height) {
  // Mapbox's globe circumference is 512 * 2^zoom pixels. Leave space around
  // the whole hemisphere on narrow phones as well as wide desktop screens.
  return Math.max(-2.5, Math.min(2.25, Math.log2(Math.max(1, Math.min(width, height)) * 0.66 * Math.PI / 512)))
}

export function createSchoolFlight(destination) {
  const zoomStart = FLIGHT_SETTLE_MS + FLIGHT_TURN_MS
  const route = geoInterpolate([GLOBE_ORIGIN.longitude, GLOBE_ORIGIN.latitude], [destination.longitude, destination.latitude])
  return (elapsed, worldZoom) => {
    const turn = flightTurnProgress((elapsed - FLIGHT_SETTLE_MS) / FLIGHT_TURN_MS)
    const zoom = clamp((elapsed - zoomStart) / FLIGHT_ZOOM_MS)
    return {
      center: route(turn),
      // Launch with momentum instead of easing from rest, then keep building
      // acceleration. Hold the globe longer so the fast dive stays visible.
      zoom: worldZoom + (13 - worldZoom) * (0.3 * zoom + 0.7 * zoom ** 3),
      opacity: 1 - smootherstep((zoom - 0.82) / 0.18),
      phase: elapsed < FLIGHT_SETTLE_MS ? 'ready' : elapsed >= zoomStart ? 'zoom' : 'turn',
      complete: elapsed >= FLIGHT_DURATION_MS,
    }
  }
}
