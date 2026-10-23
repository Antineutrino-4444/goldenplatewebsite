import test, { after, before } from 'node:test'
import assert from 'node:assert/strict'
import { fileURLToPath } from 'node:url'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

let server, usePlateApp, InterschoolPortal, MemoryRouter
const admin = { id: 'inter-admin', role: 'inter_school', name: 'Inter-school admin' }

before(async () => {
  server = await createServer({
    configFile: false,
    root: fileURLToPath(new URL('..', import.meta.url)),
    resolve: { alias: { '@': fileURLToPath(new URL('../src', import.meta.url)) } },
    esbuild: { jsx: 'automatic' },
    server: { middlewareMode: true, hmr: false, ws: false },
    optimizeDeps: { noDiscovery: true, include: [] },
    ssr: {
      noExternal: ['react-router-dom', 'react-router'],
      resolve: { conditions: ['module', 'import', 'development'] },
    },
  })
  ;({ usePlateApp } = await server.ssrLoadModule('/src/hooks/usePlateApp.js'))
  ;({ MemoryRouter } = await server.ssrLoadModule('react-router-dom'))
  ;({ default: InterschoolPortal } = await server.ssrLoadModule('/src/components/InterschoolPortal.jsx'))
})

after(async () => { await server?.close() })

function freshApp() {
  let app
  function Capture() {
    app = usePlateApp()
    return null
  }
  renderToStaticMarkup(React.createElement(Capture))
  return app
}

test('session restoration loads the inter-school overview before user state is committed', async (t) => {
  const calls = []
  t.mock.method(globalThis, 'fetch', async (url) => {
    calls.push(url)
    return { ok: true, json: async () => url.endsWith('/auth/status')
      ? { authenticated: true, user: admin }
      : { schools: [], invites: [], registration_requests: [] } }
  })
  const app = freshApp()
  assert.equal(app.user, null)
  await app.checkAuthStatus()
  assert.deepEqual(calls, ['/api/auth/status', '/api/interschool/overview'])
})

test('post-login initialization loads the overview using the login response', async (t) => {
  const calls = []
  t.mock.method(globalThis, 'fetch', async (url) => {
    calls.push(url)
    return { ok: true, json: async () => ({ schools: [], invites: [], registration_requests: [] }) }
  })
  const app = freshApp()
  await app.handlePostAuth(admin)
  assert.deepEqual(calls, ['/api/interschool/overview'])
})

test('incomplete authentication does not load the overview', async (t) => {
  const request = t.mock.method(globalThis, 'fetch', async () => { throw new Error('Unexpected request') })
  await freshApp().handlePostAuth({ ...admin, email_required: true })
  assert.equal(request.mock.callCount(), 0)
})

function portalMarkup(overrides = {}) {
  const previousWindow = globalThis.window
  globalThis.window = { location: { hostname: 'localhost' } }
  try {
    return renderToStaticMarkup(React.createElement(MemoryRouter, null,
      React.createElement(InterschoolPortal, { app: {
        latestSchoolInvites: [], interschoolSchools: [], interschoolInvites: [],
        interschoolRegistrationRequests: [], ...overrides,
      } })
    ))
  } finally {
    if (previousWindow === undefined) delete globalThis.window
    else globalThis.window = previousWindow
  }
}

test('all sections start collapsed, with pending requests first and approved requests at the bottom of the page', () => {
  const requests = [
    { id: 'a1', school_name: 'Approved newest', status: 'approved' },
    { id: 'r1', school_name: 'Rejected school', status: 'rejected' },
    { id: 'p1', school_name: 'Pending newest', status: 'pending' },
    { id: 'a2', school_name: 'Approved older', status: 'approved' },
    { id: 'p2', school_name: 'Pending older', status: 'pending' },
  ]
  const html = portalMarkup({ interschoolRegistrationRequests: requests })
  const names = ['Pending newest', 'Pending older', 'Rejected school', 'Approved newest', 'Approved older']
  const positions = names.map(name => html.indexOf(name))
  assert.ok(positions.every(position => position >= 0))
  assert.deepEqual(positions, [...positions].sort((a, b) => a - b))
  assert.equal(requests[0].id, 'a1', 'rendering must not mutate shared data')

  const sections = [...html.matchAll(/<details\b([^>]*)>([\s\S]*?)<\/details>/g)]
  assert.equal(sections.length, 8)
  for (const [, attributes, content] of sections) {
    assert.doesNotMatch(attributes, /\bopen(?:\s|=|$)/, 'every section starts closed')
    assert.match(content, /^<summary\b/, 'every section has a native keyboard-accessible toggle')
  }
  assert.match(sections[0][1], /id="pending-registrations"/)
  assert.match(sections.at(-1)[1], /id="approved-registrations"/)
  assert.match(sections[0][2], /Pending newest/)
  assert.doesNotMatch(sections[0][2], /Approved newest|Rejected school/)
  assert.match(sections.at(-1)[2], /Approved newest/)
  assert.doesNotMatch(sections.at(-1)[2], /Pending newest|Rejected school|>Approve<|>Reject</)
  assert.ok(html.indexOf('Onboarding Checklist') < html.indexOf('Approved School Registration Requests'))
})

test('loading the overview does not display misleading empty lists', () => {
  const html = portalMarkup({ interschoolOverviewLoading: true })
  for (const label of ['Loading school registration requests', 'Loading schools', 'Loading school invites']) {
    assert.ok(html.includes(label), label)
  }
  assert.doesNotMatch(html, /No school registration requests yet|No partner schools registered yet|No school invites have been issued yet/)
})
