import test from 'node:test'
import assert from 'node:assert/strict'
import { isMapHost, isSchoolPortalPath, safeReturnPath, schoolPortalUrl, siteReturnPath, sitePageLabel } from '../src/lib/navigation.js'

test('login returns to supported local pages and preserves filters', () => {
  assert.equal(safeReturnPath('/portal/dashboard?session=abc'), '/portal/dashboard?session=abc')
  assert.equal(safeReturnPath('/map?school=SAC#schools'), '/map?school=SAC#schools')
  assert.equal(safeReturnPath(null, '/interschool'), '/interschool')
})
test('school arrival includes encoded admin and dashboard login destinations', () => {
  for (const destination of ['/portal', '/portal/admin', '/portal/dashboard', '/portal/admin/?tab=accounts#invites', '/portal/dashboard?session=abc']) {
    const query = new URLSearchParams(`next=${encodeURIComponent(destination)}`)
    const target = safeReturnPath(query.get('next'))
    assert.equal(target, destination, 'the requested destination is preserved after the animation')
    assert.equal(isSchoolPortalPath(target), true, destination)
  }
  for (const destination of ['/map', '/live-counter', '/interschool', '/portal-other', '/portal/unknown']) {
    assert.equal(isSchoolPortalPath(destination), false, destination)
  }
})
test('login redirects reject off-site URLs, authentication loops, and encoded tricks', () => {
  for (const url of ['https://example.com', '//example.com', '/\\example.com', '/login', '/register', '/signup', '/%2f%2fexample.com', '/\n/map', '/unknown']) {
    assert.equal(safeReturnPath(url), '/portal', url)
  }
})
test('map subdomains link to the school portal on their corresponding main host', () => {
  assert.equal(schoolPortalUrl({ href: 'https://map.goldenplate.ca/map' }), 'https://goldenplate.ca/portal')
  assert.equal(schoolPortalUrl({ href: 'http://map.localhost:59237/' }), 'http://localhost:59237/portal')
  assert.equal(schoolPortalUrl({ href: 'http://localhost:59237/map' }), 'http://localhost:59237/portal')
  assert.equal(isMapHost('map.localhost'), true)
  assert.equal(isMapHost('goldenplate.ca'), false)
})

test('public return links preserve real local destinations and reject external paths', () => {
  for (const path of ['/', '/stories', '/stories/transcript#podcast-22-44', '/map?school=SAC', '/live-counter/community', '/guest/sessions/session-123', '/guest/schools/default-school', '/how-it-works#contact', '/getting-started#record-plates']) assert.equal(siteReturnPath(path), path)
  for (const path of ['https://example.com', '//example.com', '/\\example.com', '/%2f%2fexample.com', '/unknown', null]) assert.equal(siteReturnPath(path), '/')
  assert.equal(sitePageLabel('/how-it-works#live-counter'), 'How it works')
  assert.equal(sitePageLabel('/live-counter/community'), 'Community counter')
  assert.equal(sitePageLabel('/stories/transcript'), 'Podcast transcript')
  assert.equal(sitePageLabel('/getting-started#record-plates'), 'Getting started')
  assert.equal(sitePageLabel('/guest/schools/default-school'), 'School guest view')
})
