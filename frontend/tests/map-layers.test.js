import test from 'node:test'
import assert from 'node:assert/strict'
import { applyBasemap, isPublicMapboxToken, MAP_LAYERS_KEY, MAP_WORLDVIEW, MAP_LANGUAGE, mapStyleFor, readMapLayers, SATELLITE_STYLE, STREET_STYLE, streetViewUrl } from '../src/lib/mapLayers.js'

test('maps always start in hybrid while preserving the school-pin preference', () => {
  const defaults = { basemap: 'hybrid', showSchools: true }
  assert.deepEqual(readMapLayers(), defaults)
  assert.deepEqual(readMapLayers({ getItem: () => '{broken' }), defaults)
  assert.deepEqual(readMapLayers({ getItem: () => { throw new Error('blocked') } }), defaults)
  assert.deepEqual(readMapLayers({ getItem: () => '{"basemap":"unknown"}' }), defaults)
  assert.deepEqual(readMapLayers({ getItem: () => '{"basemap":"street"}' }), defaults)
  assert.deepEqual(readMapLayers({ getItem: () => '{"basemap":"satellite","showSchools":false}' }), { basemap: 'hybrid', showSchools: false })
  assert.deepEqual(readMapLayers({ getItem: (key) => {
    assert.equal(key, MAP_LAYERS_KEY)
    return '{"basemap":"hybrid","showSchools":false}'
  } }), { basemap: 'hybrid', showSchools: false })
})

test('every Mapbox presentation uses English with the CN worldview and retains boundaries', () => {
  assert.equal(MAP_WORLDVIEW, 'CN')
  assert.equal(MAP_LANGUAGE, 'en')
  for (const mode of ['street', 'hybrid', 'satellite']) {
    const style = mapStyleFor(mode)
    const basemap = style.imports[0]
    assert.equal(style.version, 8)
    assert.equal(basemap.id, 'basemap')
    assert.equal(basemap.url, mode === 'street' ? STREET_STYLE : SATELLITE_STYLE)
    assert.equal(basemap.config.showAdminBoundaries, true)
    assert.equal(basemap.config.showPlaceLabels, true)
    assert.equal(basemap.config.showRoadLabels, mode !== 'satellite')
    if (mode !== 'street') assert.equal(basemap.config.showRoadsAndTransit, mode === 'hybrid')
  }
})

test('layer changes configure shared imagery and restore hybrid references', () => {
  let style = mapStyleFor('hybrid')
  let reloads = 0
  const map = {
    getStyle: () => style,
    setProjection: (value) => assert.equal(value, null),
    setConfig: (id, config) => { assert.equal(id, 'basemap'); style.imports[0].config = config },
    setStyle: (next) => { reloads += 1; style = next },
  }
  applyBasemap(map, 'satellite')
  assert.equal(reloads, 0)
  assert.equal(style.imports[0].config.showRoadLabels, false)
  applyBasemap(map, 'hybrid')
  assert.equal(reloads, 0)
  assert.equal(style.imports[0].config.showRoadLabels, true)
  applyBasemap(map, 'street')
  assert.equal(reloads, 1)
  assert.equal(style.imports[0].url, STREET_STYLE)
  applyBasemap(map, 'hybrid')
  assert.equal(reloads, 2)
  assert.equal(style.imports[0].url, SATELLITE_STYLE)
  assert.equal(style.imports[0].config.showAdminBoundaries, true)
})

test('only public browser tokens enable Mapbox, never secret tokens or placeholders', () => {
  assert.equal(isPublicMapboxToken(' pk.test_payload.test_signature '), true)
  for (const value of ['', 'pk.', 'pk.your_token', 'sk.test_payload.test_signature', 'YOUR_MAPBOX_ACCESS_TOKEN', null]) {
    assert.equal(isPublicMapboxToken(value), false)
  }
})

test('Street View links use geographic coordinates and never invent an unmapped school location', () => {
  const link = new URL(streetViewUrl({ latitude: 44.01213, longitude: -79.47816 }))
  assert.equal(link.origin, 'https://www.google.com')
  assert.equal(link.searchParams.get('api'), '1')
  assert.equal(link.searchParams.get('map_action'), 'pano')
  assert.equal(link.searchParams.get('viewpoint'), '44.01213,-79.47816')
  assert.equal(link.searchParams.get('hl'), 'en')
  assert.equal(streetViewUrl({ latitude: null, longitude: null }), null)
  assert.equal(streetViewUrl({ latitude: 91, longitude: 0 }), null)
})
