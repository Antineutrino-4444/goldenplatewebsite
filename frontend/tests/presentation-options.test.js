import test from 'node:test'
import assert from 'node:assert/strict'
import { assemblyAction, liveProviders, liveReturnNotice, needsGoogleSlidesNotice, presentationLoginPath, readPresentationOptions, schoolLabelOption } from '../src/lib/presentation-options.js'

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
      assert.equal(assemblyAction(format, live, true, true).label, 'Update live ' + product + ' deck')
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

test('Google format differences are shown for new files and connections, with one-click access to existing decks', () => {
  for (const action of ['manual', 'google']) {
    assert.equal(needsGoogleSlidesNotice(action, 'google-slides', { status: 'ready', url: 'existing' }), true)
  }
  assert.equal(needsGoogleSlidesNotice('live', 'google-slides', null), true)
  assert.equal(needsGoogleSlidesNotice('live', 'google-slides', { status: 'reconnect', url: 'existing' }), true)
  for (const status of ['pending', 'ready', 'retry']) {
    assert.equal(needsGoogleSlidesNotice('live', 'google-slides', { status }), false)
  }
  assert.equal(needsGoogleSlidesNotice('live', 'pptx', null), false)
  assert.equal(needsGoogleSlidesNotice('download', 'pdf', null), false)
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
        kind: 'assembly', format, linkedTheme: 'dark', schoolCode: 'SAC', schoolLabel: null,
      })
    }
  }
})

test('new assembly forms default to PowerPoint and do not pin the appearance', () => {
  assert.deepEqual(readPresentationOptions(''), {
    kind: 'assembly', format: 'pptx', linkedTheme: null, schoolCode: '', schoolLabel: null,
  })
  assert.deepEqual(readPresentationOptions('?format=unknown&theme=unknown'), {
    kind: 'assembly', format: 'pptx', linkedTheme: null, schoolCode: '', schoolLabel: null,
  })
})

test('signing in returns to the exporter with the selected school, format, theme and label', () => {
  const origin = 'https://goldenplate.test'
  for (const [schoolLabel, expected] of [[undefined, null], ['', ''], ['  École  A&B  ', 'École A&B']]) {
    const login = new URL(presentationLoginPath({ format: 'google-slides', theme: 'light', schoolCode: ' A&B ', schoolLabel }), origin)
    assert.equal(login.pathname, '/login')
    const destination = new URL(login.searchParams.get('next'), origin)
    assert.equal(destination.pathname, '/export')
    assert.deepEqual(readPresentationOptions(destination.search), {
      kind: 'assembly', format: 'google-slides', linkedTheme: 'light', schoolCode: 'A&B', schoolLabel: expected,
    })
  }
})

test('an untouched live label, custom label and explicit reset send distinct options', () => {
  assert.deepEqual(schoolLabelOption(null), {})
  assert.deepEqual(schoolLabelOption(undefined), {})
  assert.deepEqual(schoolLabelOption('   '), { school_label: '' })
  assert.deepEqual(schoolLabelOption('  Upper   School 🦉  '), { school_label: 'Upper School 🦉' })
})
