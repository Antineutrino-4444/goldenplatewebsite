import { geoInterpolate } from 'd3-geo'
import { GLOBE_ORIGIN } from './globe-origin.js'

export const FLIGHT_TURN_MS = 1600
export const FLIGHT_ZOOM_MS = 1400
export const FLIGHT_TARGET_ZOOM = 18
export const FLIGHT_SETTLE_MS = 150
export const FLIGHT_ZOOM_END_MS = FLIGHT_SETTLE_MS + FLIGHT_TURN_MS + FLIGHT_ZOOM_MS
export const FLIGHT_REVEAL_MS = 400
export const FLIGHT_REVEAL_START_MS = FLIGHT_ZOOM_END_MS - 300
export const FLIGHT_DURATION_MS = FLIGHT_REVEAL_START_MS + FLIGHT_REVEAL_MS
const clamp = (value) => Math.max(0, Math.min(1, value))

// Some satellite sources keep the map's global load event pending even after
// the globe has rendered. Allow that visible frame to start playback shortly.
export function schoolFlightReadiness(onStart, { setTimer = setTimeout, clearTimer = clearTimeout } = {}) {
  let timer, started = false, disposed = false
  const start = () => {
    if (started || disposed) return
    started = true
    clearTimer(timer)
    onStart()
  }
  return {
    rendered() {
      if (!started && !disposed && timer === undefined) timer = setTimer(start, 1200)
    },
    loaded: start,
    dispose() { disposed = true; clearTimer(timer) },
  }
}

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

function diveProgress(value) {
  return value ** 8
}

export function flightRevealProgress(value) {
  // Fade across the final dive and finish just after the camera arrives.
  return smootherstep(value)
}

export function fullGlobeZoom(width, height) {
  // Mapbox's globe circumference is 512 * 2^zoom pixels. Leave space around
  // the whole hemisphere on narrow phones as well as wide desktop screens.
  return Math.max(-2.5, Math.min(2.25, Math.log2(Math.max(1, Math.min(width, height)) * 0.66 * Math.PI / 512)))
}

export function createSchoolFlight(destination) {
  const zoomStart = FLIGHT_SETTLE_MS + FLIGHT_TURN_MS
  const target = [destination.longitude, destination.latitude]
  const route = geoInterpolate([GLOBE_ORIGIN.longitude, GLOBE_ORIGIN.latitude], target)
  return (elapsed, worldZoom) => {
    const turn = flightTurnProgress((elapsed - FLIGHT_SETTLE_MS) / FLIGHT_TURN_MS)
    const zoom = clamp((elapsed - zoomStart) / FLIGHT_ZOOM_MS)
    return {
      // Once the turn ends, keep the camera on the exact saved coordinates.
      center: elapsed >= zoomStart ? target : route(turn),
      // Barely move through the opening, then drive most of the dive through
      // the last quarter with continuously increasing speed and acceleration.
      zoom: worldZoom + (FLIGHT_TARGET_ZOOM - worldZoom) * diveProgress(zoom),
      // Reveal on an independent clock without blending or slowing the camera.
      reveal: flightRevealProgress((elapsed - FLIGHT_REVEAL_START_MS) / FLIGHT_REVEAL_MS),
      phase: elapsed < FLIGHT_SETTLE_MS ? 'ready' : elapsed >= zoomStart ? 'zoom' : 'turn',
      complete: elapsed >= FLIGHT_DURATION_MS,
    }
  }
}
