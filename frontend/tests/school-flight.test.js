import test from 'node:test'
import assert from 'node:assert/strict'
import { geoDistance } from 'd3-geo'
import { createSchoolFlight, FLIGHT_DURATION_MS, FLIGHT_SETTLE_MS, FLIGHT_TURN_MS, FLIGHT_ZOOM_MS, flightTurnProgress, fullGlobeZoom, schoolFlightDeadline } from '../src/lib/school-flight.js'

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

test('school travel follows a shortest spherical arc without zooming or fading', () => {
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
  assert.equal(middle.opacity, 1)
  assert.equal(middle.phase, 'turn')
})

test('the turn arrives before a faster zoom with increasing acceleration and a continuous portal fade', () => {
  const flight = createSchoolFlight(school)
  const zoomStart = FLIGHT_SETTLE_MS + FLIGHT_TURN_MS
  const samples = [0, 0.25, 0.5, 0.75, 1].map((t) => flight(zoomStart + t * FLIGHT_ZOOM_MS, 1))
  for (const sample of samples) {
    assert.ok(geoDistance(sample.center, [school.longitude, school.latitude]) < 1e-8)
  }
  const increments = samples.slice(1).map((sample, index) => sample.zoom - samples[index].zoom)
  assert.ok(increments.every((value, index) => index === 0 || value > increments[index - 1]))
  const accelerations = increments.slice(1).map((value, index) => value - increments[index])
  assert.ok(accelerations.every((value, index) => value > 0 && (index === 0 || value > accelerations[index - 1])))
  assert.ok(FLIGHT_ZOOM_MS <= 650, 'zoom completes in at most 650 milliseconds')
  const launch = flight(zoomStart + FLIGHT_ZOOM_MS * 0.1, 1)
  assert.ok(launch.zoom > 1.36, 'zoom starts with momentum instead of lingering at world scale')
  assert.equal(samples[2].opacity, 1)
  assert.equal(samples[3].opacity, 1, 'keep the accelerating dive visible before fading')
  const fade = flight(zoomStart + FLIGHT_ZOOM_MS * 0.9, 1)
  assert.ok(fade.opacity > 0 && fade.opacity < 1)
  assert.equal(samples[4].opacity, 0)
  assert.equal(samples[4].zoom, 13)
  assert.equal(flight(FLIGHT_DURATION_MS, 1).complete, true)
  assert.equal(flight(FLIGHT_DURATION_MS - 1, 1).complete, false)
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
  assert.equal(FLIGHT_DURATION_MS, 2400)
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
