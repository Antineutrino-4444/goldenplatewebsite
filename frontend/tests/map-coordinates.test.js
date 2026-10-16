import test from 'node:test'
import assert from 'node:assert/strict'
import { hasGeographicCoordinates, wrapLongitude, formatCoordinates } from '../src/lib/mapCoordinates.js'
import { maxSchoolSessions, schoolActivity, schoolSessionLabel, schoolsWithoutLocations, submissionsInOthers } from '../src/lib/schoolMap.js'

test('pins scale relative to the community leader without a fixed session threshold', () => {
  const levels = [0, 1, 5, 25, 100, 10000].map(count => schoolActivity(count, 10000))
  assert.equal(levels[0].width, 30)
  for (let i = 1; i < levels.length; i++) {
    assert.ok(levels[i].width > levels[i - 1].width)
    assert.ok(levels[i].emphasis > levels[i - 1].emphasis)
    assert.ok(levels[i].width <= 48 && levels[i].height <= 60)
  }
  assert.equal(levels.at(-1).emphasis, 1)
  assert.equal(schoolActivity(8, 8).width, schoolActivity(10000, 10000).width)
  assert.ok(schoolActivity(8, 8).width > schoolActivity(8, 100).width)
  for (const invalid of [undefined, null, '12', NaN, Infinity, -20]) {
    assert.deepEqual(schoolActivity(invalid, 100), schoolActivity(0, 100))
    assert.ok(Number.isFinite(schoolActivity(12, invalid).width))
  }
  assert.equal(schoolActivity(0, 0).emphasis, 0)
  assert.equal(schoolSessionLabel(1), '1 public session')
  assert.equal(schoolSessionLabel(1200), '1,200 public sessions')
})

test('activity reference includes unmapped schools and ignores invalid counts', () => {
  const schools = [
    { school_id: 'mapped', session_count: 8, latitude: 0, longitude: 0 },
    { school_id: 'unmapped', session_count: 50, latitude: null, longitude: null },
    { school_id: 'pending', session_count: undefined },
  ]
  const maximum = maxSchoolSessions(schools)
  assert.equal(maximum, 50)
  assert.ok(schoolActivity(8, maximum).emphasis < 1)
  assert.equal(maxSchoolSessions([]), 0)
  assert.equal(maxSchoolSessions([{ session_count: Infinity }, { session_count: -4 }]), 0)
})

test('image coordinates never become geographic positions', () => {
  for (const point of [{ x: 50, y: 50 }, { latitude: null, longitude: null },
    { latitude: 12 }, { latitude: '12', longitude: '15' }]) {
    assert.equal(hasGeographicCoordinates(point), false)
  }
  assert.equal(hasGeographicCoordinates({ latitude: 0, longitude: 0 }), true)
  assert.equal(hasGeographicCoordinates({ latitude: 91, longitude: 0 }), false)
  assert.equal(hasGeographicCoordinates({ latitude: 0, longitude: Infinity }), false)
})

test('longitude wraps safely across the date line', () => {
  assert.equal(wrapLongitude(190), -170)
  assert.equal(wrapLongitude(-190), 170)
  assert.equal(wrapLongitude(-79), -79)
})

test('coordinate labels show geographic directions', () => {
  assert.equal(formatCoordinates({ latitude: 43.99, longitude: -79.47 }), '43.99000° N, 79.47000° W')
  assert.equal(formatCoordinates({ x: 10, y: 20 }), 'No location set yet')
})

test('both undecided schools and schools choosing to remain unmapped belong in Others', () => {
  const schools = [
    { school_id: 'pending', location_state: 'pending', latitude: null, longitude: null },
    { school_id: 'unmapped', location_state: 'unmapped', latitude: null, longitude: null },
    { school_id: 'mapped', latitude: 0, longitude: 0 },
  ]
  assert.deepEqual(schoolsWithoutLocations(schools).map((school) => school.school_id), ['pending', 'unmapped'])
  const updates = [
    { id: 'pending-update', school_id: 'pending', pin_id: 'old-pin' },
    { id: 'unmapped-update', school_id: 'unmapped', pin_id: 'old-pin' },
    { id: 'unplaced-update', school_id: 'mapped', pin_id: null },
    { id: 'mapped-update', school_id: 'mapped', pin_id: 'world-pin' },
  ]
  assert.deepEqual(submissionsInOthers(updates, schools).map((update) => update.id),
    ['pending-update', 'unmapped-update', 'unplaced-update'])
})

