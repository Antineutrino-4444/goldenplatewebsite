import test from 'node:test'
import assert from 'node:assert/strict'
import { fileURLToPath } from 'node:url'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'
import { deckStatus, deckTime, deckUrl } from '../src/lib/live-decks.js'

test('connection status distinguishes an upload lease from a queued request', () => {
  const now = Date.parse('2026-11-24T19:00:00Z')
  assert.equal(deckStatus({ status: 'pending' }, now), 'Update queued')
  assert.equal(deckStatus({ status: 'pending', lease_until: '2026-11-24T19:05:00Z' }, now), 'Syncing…')
  assert.equal(deckStatus({ status: 'pending', lease_until: '2026-11-24T18:59:00Z' }, now), 'Update queued')
  for (const status of ['ready', 'retry']) {
    assert.equal(deckStatus({ status, lease_until: '2026-11-24T19:05:00Z' }, now), 'Syncing…')
  }
  assert.equal(deckStatus({ status: 'retry' }), 'Update failed')
  assert.equal(deckTime(null), 'Not synced yet')
  assert.equal(deckTime('invalid'), 'Not synced yet')
})

test('only HTTPS deck links without embedded credentials become navigable', () => {
  assert.equal(deckUrl('https://docs.google.com/presentation/d/example/edit'), 'https://docs.google.com/presentation/d/example/edit')
  for (const value of ['javascript:alert(1)', 'http://example.test/file', 'https://secret@example.test/file', '/relative', null]) {
    assert.equal(deckUrl(value), null)
  }
})

test('connection rows show service details and safe recovery controls for both surfaces', async () => {
  const server = await createServer({
    configFile: false, root: fileURLToPath(new URL('..', import.meta.url)),
    esbuild: { jsx: 'automatic' },
    resolve: { alias: { '@': fileURLToPath(new URL('../src', import.meta.url)) } },
    server: { middlewareMode: true, ws: false }, optimizeDeps: { noDiscovery: true, include: [] },
  })
  try {
    const { default: Connections } = await server.ssrLoadModule('/src/components/LiveDeckConnections.jsx')
    const props = { providers: { google: true, microsoft: true }, onSync() {}, schoolCode: 'SAC', connections: [{
      id: 'example', provider: 'google', theme: 'dark', status: 'retry',
      message: 'The presentation changed while syncing.', url: 'https://docs.google.com/presentation/d/example/edit',
      owner_name: 'Connection owner', owner_username: 'owner', last_synced_at: '2026-11-24T19:00:00Z',
    }] }
    const own = renderToStaticMarkup(React.createElement(Connections, props))
    assert.match(own, /Google Slides/)
    assert.match(own, /Dark/)
    assert.match(own, /Sync now/)
    assert.match(own, /Open deck/)
    assert.match(own, /Last synced:/)
    assert.match(own, /The presentation changed while syncing/)
    assert.doesNotMatch(own, /Connection owner/)
    const admin = renderToStaticMarkup(React.createElement(Connections, { ...props, admin: true }))
    assert.match(admin, /Connected by Connection owner/)
    assert.match(admin, /PowerPoint \/ OneDrive: Configured/)
    const reconnect = renderToStaticMarkup(React.createElement(Connections, { ...props,
      connections: [{ ...props.connections[0], status: 'reconnect', url: 'javascript:secret' }],
    }))
    assert.match(reconnect, /Reconnect required/)
    assert.match(reconnect, /school=SAC&amp;theme=dark&amp;format=google-slides/)
    assert.doesNotMatch(reconnect, /javascript:secret|Sync now/)
  } finally { await server.close() }
})
