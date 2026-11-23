import test from 'node:test'
import assert from 'node:assert/strict'
import { assemblyAction, liveProviders, liveReturnNotice, presentationLoginPath, readPresentationOptions } from '../src/lib/presentation-options.js'

test('live assembly actions reuse the connected deck and respect its provider and status', () => {
  assert.deepEqual(liveProviders, { pptx: 'microsoft', 'google-slides': 'google' })
  for (const [format, product] of [['pptx', 'PowerPoint'], ['google-slides', 'Google Slides']]) {
    const live = { enabled: true, link: null }
    assert.deepEqual(assemblyAction(format, live, true), { value: 'live', label: 'Create live ' + product + ' deck' })
    live.link = { status: 'pending' }
    assert.equal(assemblyAction(format, live, true).label, 'Check live ' + product + ' deck')
    for (const status of ['ready', 'retry']) {
      live.link = { status, url: 'https://example.org/existing' }
      assert.equal(assemblyAction(format, live, true).label, 'Open live ' + product + ' deck')
    }
    live.link.status = 'reconnect'
    assert.equal(assemblyAction(format, live, true).label, 'Reconnect ' + product)
  }
})

test('snapshot-only deployments retain the direct Google flow and the manual downloads', () => {
  const disabled = { enabled: false, link: null }
  assert.equal(assemblyAction('google-slides', disabled, true).value, 'google')
  assert.equal(assemblyAction('google-slides', disabled, false).value, 'manual')
  assert.equal(assemblyAction('pptx', disabled, false).value, 'download')
  assert.equal(assemblyAction('pdf', disabled, false).value, 'download')
})

test('a cloud callback gives a safe recovery message and never displays arbitrary return parameters', () => {
  assert.equal(liveReturnNotice('?school=demo'), null)
  assert.equal(liveReturnNotice('?live_error=authorization').type, 'error')
  for (const value of ['__proto__', 'confidential-detail']) {
    assert.ok(!liveReturnNotice('?live_error=' + value).message.includes(value))
  }
})

test('saved presentation links open the full school assembly and preserve download settings', () => {
  for (const kind of ['assembly', 'overview', 'introduction', 'template', 'unknown']) {
    for (const format of ['pptx', 'google-slides', 'pdf']) {
      const query = new URLSearchParams({ presentation: kind, format, theme: 'dark', school: 'SAC' })
      assert.deepEqual(readPresentationOptions(query.toString()), {
        kind: 'assembly', format, theme: 'dark', schoolCode: 'SAC',
      })
    }
  }
})

test('a new assembly defaults to PowerPoint and uses the current site theme', () => {
  assert.deepEqual(readPresentationOptions(''), {
    kind: 'assembly', format: 'pptx', theme: 'light', schoolCode: '',
  })
  assert.deepEqual(readPresentationOptions('?format=unknown&theme=unknown', 'dark'), {
    kind: 'assembly', format: 'pptx', theme: 'dark', schoolCode: '',
  })
})

test('signing in returns to the assembly section with the selected school, format and theme', () => {
  const origin = 'https://goldenplate.test'
  const options = readPresentationOptions('?presentation=overview&format=google-slides&theme=light')
  const login = new URL(presentationLoginPath({ ...options, schoolCode: ' A&B ' }), origin)
  assert.equal(login.pathname, '/login')
  const destination = new URL(login.searchParams.get('next'), origin)
  assert.equal(destination.pathname, '/resources')
  assert.equal(destination.hash, '#assembly')
  assert.deepEqual(readPresentationOptions(destination.search), {
    kind: 'assembly', format: 'google-slides', theme: 'light', schoolCode: 'A&B',
  })
})
