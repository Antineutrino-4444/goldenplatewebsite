import test from 'node:test'
import assert from 'node:assert/strict'
import { schoolGuestPath } from '../src/lib/schoolMap.js'

test('school guest links use the selected school identity, including schools without coordinates', () => {
  assert.equal(schoolGuestPath({ school_id: 'school-123', latitude: null, longitude: null }), '/guest/schools/school-123')
  assert.equal(schoolGuestPath({ school_id: 'school-456' }), '/guest/schools/school-456')
  assert.equal(schoolGuestPath({ school_id: 'x/?#' }), '/guest/schools/x%2F%3F%23')
  for (const school of [null, {}, { id: 'map-pin-only' }, { school_id: '' }, { school_id: ' ' }]) assert.equal(schoolGuestPath(school), null)
})
