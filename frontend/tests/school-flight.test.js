import test from 'node:test'
import assert from 'node:assert/strict'
import { geoDistance } from 'd3-geo'
import { createSchoolFlight, FLIGHT_DURATION_MS, FLIGHT_REVEAL_MS, FLIGHT_REVEAL_START_MS, FLIGHT_SETTLE_MS, FLIGHT_TARGET_ZOOM, FLIGHT_TURN_MS, FLIGHT_ZOOM_END_MS, FLIGHT_ZOOM_MS, flightRevealProgress, flightTurnProgress, fullGlobeZoom, schoolFlightDeadline, schoolFlightReadiness } from '../src/lib/school-flight.js'

import { GLOBE_ORIGIN } from '../src/lib/globe-origin.js'

const school = { longitude: -79.46, latitude: 44 }

function flightClock() {
  let now = 0, nextId = 0
  const timers = new Map()
  return {
    setTimer(fn, delay) { const id = ++nextId; timers.set(id, { fn, at: now + delay }); return id },
    clearTimer(id) { timers.delete(id) },
    advance(ms) {
      now += ms
      for (const [id, timer] of timers) if (timer.at <= now) { timers.delete(id); timer.fn() }
    },
  }
}

test('a rendered globe starts playback even when satellite requests hold the load event open', () => {
  const clock = flightClock()
  let starts = 0
  const readiness = schoolFlightReadiness(() => starts++, clock)
  clock.advance(10000)
  assert.equal(starts, 0, 'wait for an actual rendered frame')
  readiness.rendered()
  clock.advance(1199)
  assert.equal(starts, 0)
  readiness.rendered()
  clock.advance(1)
  assert.equal(starts, 1, 'repeated rendered frames do not postpone playback')
  readiness.loaded()
  assert.equal(starts, 1, 'a late load event cannot start a second animation')
})

test('normal loading starts immediately and cleanup cancels a pending playback start', () => {
  const clock = flightClock()
  let starts = 0
  const readiness = schoolFlightReadiness(() => starts++, clock)
  readiness.rendered()
  readiness.loaded()
  assert.equal(starts, 1)
  clock.advance(1200)
  assert.equal(starts, 1)
  const cancelled = schoolFlightReadiness(() => starts++, clock)
  cancelled.rendered()
  cancelled.dispose()
  clock.advance(1200)
  cancelled.loaded()
  assert.equal(starts, 1)
})

test('a slow globe load does not shorten the actual login flight', () => {
  const clock = flightClock()
  let completed = 0
  const deadline = schoolFlightDeadline(() => completed++, clock)
  clock.advance(11000)
  deadline.ready()
  clock.advance(FLIGHT_DURATION_MS)
  assert.equal(completed, 0, 'the full camera sequence can finish after a slow load')
  deadline.ready() // Camera frames do not repeatedly extend the safety deadline.
  clock.advance(3000)
  assert.equal(completed, 1)
})

test('an unavailable globe still exits and unmounting cancels the safety deadline', () => {
  const clock = flightClock()
  let completed = 0
  schoolFlightDeadline(() => completed++, clock)
  clock.advance(12000)
  assert.equal(completed, 1)
  const cancelled = schoolFlightDeadline(() => completed++, clock)
  cancelled.ready()
  cancelled.dispose()
  clock.advance(20000)
  assert.equal(completed, 1)
})

test('the globe has a dramatic, symmetric surge and slowdown during the turn', () => {
  const values = [0, 0.25, 0.5, 0.75, 1].map(flightTurnProgress)
  const travel = values.slice(1).map((value, index) => value - values[index])
  assert.equal(values[0], 0)
  assert.equal(values.at(-1), 1)
  assert.ok(travel[0] < travel[1] && travel[3] < travel[2])
  assert.ok(travel[1] > travel[0] * 20, 'most travel happens around the middle of the turn')
  assert.ok(Math.abs(travel[0] - travel[3]) < 1e-8)
  assert.ok(Math.abs(travel[1] - travel[2]) < 1e-8)
  assert.equal(flightTurnProgress(-1), 0)
  assert.equal(flightTurnProgress(2), 1)
})

test('school travel follows a shortest spherical arc before zooming or revealing the portal', () => {
  const origin = [GLOBE_ORIGIN.longitude, GLOBE_ORIGIN.latitude]
  const destination = { longitude: -140, latitude: 40 }
  const end = [destination.longitude, destination.latitude]
  const flight = createSchoolFlight(destination)
  const middle = flight(FLIGHT_SETTLE_MS + FLIGHT_TURN_MS / 2, 1)
  const firstHalf = geoDistance(origin, middle.center)
  const secondHalf = geoDistance(middle.center, end)
  assert.ok(Math.abs(firstHalf - secondHalf) < 1e-8)
  assert.ok(Math.abs(firstHalf + secondHalf - geoDistance(origin, end)) < 1e-8)
  assert.equal(middle.zoom, 1)
  assert.equal(middle.reveal, 0)
  assert.equal(middle.phase, 'turn')
})

test('the turn arrives before a slow-start zoom with sharply increasing acceleration and a late portal reveal', () => {
  const flight = createSchoolFlight(school)
  const zoomStart = FLIGHT_SETTLE_MS + FLIGHT_TURN_MS
  const samples = [0, 0.25, 0.5, 0.75, 1].map((t) => flight(zoomStart + t * FLIGHT_ZOOM_MS, 1))
  for (const sample of samples) {
    assert.deepEqual(sample.center, [school.longitude, school.latitude], 'the zoom keeps the camera on the exact destination')
  }
  const increments = samples.slice(1).map((sample, index) => sample.zoom - samples[index].zoom)
  assert.ok(increments.every((value, index) => index === 0 || value > increments[index - 1]))
  const accelerations = increments.slice(1).map((value, index) => value - increments[index])
  assert.ok(accelerations.every((value, index) => value > 0 && (index === 0 || value > accelerations[index - 1])))
  assert.ok(FLIGHT_ZOOM_MS >= 1200 && FLIGHT_ZOOM_MS <= 1500, 'keep the slow opening but compress the final dive')
  const launch = flight(zoomStart + FLIGHT_ZOOM_MS * 0.1, 1)
  assert.ok(launch.zoom > 1 && launch.zoom < 1.01, 'the first tenth should be almost still')
  assert.ok(samples[2].zoom < 1.08, 'the first half is nearly motionless at globe scale')
  assert.ok(samples[3].zoom < 3, 'even three quarters through, the camera is still near globe scale')
  assert.ok(increments[3] > increments[0] * 1000, 'the final quarter travels dramatically farther than the opening quarter')
  const finalFifth = FLIGHT_TARGET_ZOOM - flight(zoomStart + FLIGHT_ZOOM_MS * 0.8, 1).zoom
  assert.ok(finalFifth > (FLIGHT_TARGET_ZOOM - 1) * 0.8, 'over 80% of the zoom-level change happens in the final fifth')
  assert.ok(FLIGHT_TARGET_ZOOM >= 18, 'finish at building scale rather than stopping over the neighbourhood')
  const finalHundredMs = FLIGHT_TARGET_ZOOM - flight(FLIGHT_ZOOM_END_MS - 100, 1).zoom
  assert.ok(finalHundredMs > 7, 'the final 100 ms must continue a fast dive instead of easing to a stop')
  assert.equal(samples[2].reveal, 0)
  assert.ok(samples[3].reveal < 0.05, 'the portal starts appearing as the final dive gathers speed')
  assert.equal(flight(zoomStart + FLIGHT_ZOOM_MS * 0.7, 1).reveal, 0)
  assert.ok(samples[4].reveal > 0.8 && samples[4].reveal < 1)
  assert.equal(samples[4].zoom, FLIGHT_TARGET_ZOOM)
  assert.equal(flight(FLIGHT_DURATION_MS, 1).complete, true)
  assert.equal(flight(FLIGHT_DURATION_MS - 1, 1).complete, false)
})

test('the fade overlaps the final dive without changing the camera', () => {
  const flight = createSchoolFlight(school)
  assert.equal(FLIGHT_ZOOM_MS, 1400)
  assert.equal(FLIGHT_ZOOM_END_MS, 3150)
  assert.equal(FLIGHT_REVEAL_MS, 400)
  assert.equal(FLIGHT_REVEAL_START_MS, FLIGHT_ZOOM_END_MS - 300)
  assert.equal(flight(FLIGHT_REVEAL_START_MS, 1).reveal, 0)
  const midpoint = flight(FLIGHT_REVEAL_START_MS + FLIGHT_REVEAL_MS / 2, 1).reveal
  assert.equal(midpoint, 0.5)
  assert.equal(flight(FLIGHT_ZOOM_END_MS, 1).zoom, 18)
  assert.equal(flight(FLIGHT_ZOOM_END_MS, 1).complete, false, 'keep the overlay mounted through the end of the reveal')
  for (const offset of [0, 50, 150, 299]) {
    const sample = flight(FLIGHT_ZOOM_END_MS + offset, 1)
    assert.equal(sample.zoom, 18)
    assert.deepEqual(sample.center, [school.longitude, school.latitude])
  }
  assert.equal(flight(FLIGHT_DURATION_MS, 1).reveal, 1)
  assert.equal(flight(FLIGHT_DURATION_MS, 1).complete, true)
})

test('the fade is bounded, smooth and clears completely', () => {
  assert.equal(flightRevealProgress(-1), 0)
  assert.equal(flightRevealProgress(0), 0)
  assert.equal(flightRevealProgress(0.5), 0.5)
  assert.equal(flightRevealProgress(1), 1)
  assert.equal(flightRevealProgress(2), 1)
  const samples = [0, 0.25, 0.5, 0.75, 1].map(flightRevealProgress)
  assert.ok(samples.every((value, index) => index === 0 || value > samples[index - 1]))
})

test('full-globe framing fits phones, landscape, tablets, desktop and resizing', () => {
  for (const [width, height] of [[390, 844], [844, 390], [768, 1024], [1440, 1050]]) {
    const zoom = fullGlobeZoom(width, height)
    const diameter = 512 * 2 ** zoom / Math.PI
    assert.ok(diameter < Math.min(width, height) * 0.7)
    assert.ok(zoom >= -2.5 && zoom <= 2.25)
  }
  assert.equal(fullGlobeZoom(390, 844), fullGlobeZoom(844, 390))
})

test('every flight starts over Jiamusi hospital, including destinations nearby', () => {
  assert.equal(FLIGHT_DURATION_MS, 3250)
  for (const destination of [school, { longitude: 130.32, latitude: 46.81 }, { longitude: 151.2, latitude: -33.87 }]) {
    const flight = createSchoolFlight(destination)
    const opening = flight(0, 1)
    assert.ok(geoDistance(opening.center, [GLOBE_ORIGIN.longitude, GLOBE_ORIGIN.latitude]) < 1e-8)
    assert.equal(opening.phase, 'ready')
    assert.equal(opening.zoom, 1)
    assert.equal(flight(FLIGHT_SETTLE_MS + FLIGHT_TURN_MS / 2, 1).phase, 'turn')
    assert.equal(flight(FLIGHT_DURATION_MS - 1, 1).complete, false)
    const final = flight(FLIGHT_DURATION_MS, 1)
    assert.ok(geoDistance(final.center, [destination.longitude, destination.latitude]) < 1e-8)
    assert.equal(final.complete, true)
  }
})
