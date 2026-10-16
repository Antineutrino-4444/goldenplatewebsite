import test from 'node:test'
import assert from 'node:assert/strict'
import { projectionFor, readMapView, schoolBounds } from '../src/lib/mapView.js'

test('globe and flat preferences use their actual map projections', () => {
  assert.equal(readMapView({ getItem: () => 'flat' }), 'flat')
  assert.equal(readMapView({ getItem: () => 'broken-value' }), 'globe')
  assert.equal(readMapView({ getItem: () => { throw new Error('blocked') } }), 'globe')
  assert.deepEqual(projectionFor('flat'), { name: 'mercator' })
  assert.deepEqual(projectionFor('globe'), { name: 'globe' })
})

test('show schools fits locations across the date line without spanning the whole world', () => {
  const bounds = schoolBounds([{ longitude: 179, latitude: 10 }, { longitude: -179, latitude: -10 }])
  assert.equal(bounds[1][0] - bounds[0][0], 2)
  assert.equal(bounds[0][1], -10)
  assert.equal(bounds[1][1], 10)
  assert.equal(schoolBounds([]), null)
})
