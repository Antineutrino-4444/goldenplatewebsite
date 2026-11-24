import assert from 'node:assert/strict'
import { Buffer } from 'node:buffer'
import { test } from 'node:test'
import { authorizeGoogleSlides, createGoogleSlidesFile, loadGoogleSlidesAuth } from '../src/lib/google-slides.js'

const scope = 'https://www.googleapis.com/auth/drive.file'
const nativeMime = 'application/vnd.google-apps.presentation'
const sourceMime = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'

function fakeGoogle(t, onRequest) {
  const oauth2 = { initTokenClient: config => ({ requestAccessToken: () => onRequest(config) }) }
  globalThis.window = { google: { accounts: { oauth2 } } }
  t.after(() => { delete globalThis.window })
}

test('coalesces script loads, removes failed loads and can retry', async t => {
  const scripts = []
  globalThis.window = {}
  globalThis.document = {
    createElement: () => ({ remove() { this.removed = true } }),
    head: { appendChild(script) { scripts.push(script) } },
  }
  t.after(() => { delete globalThis.document; delete globalThis.window })
  const first = loadGoogleSlidesAuth()
  assert.equal(loadGoogleSlidesAuth(), first)
  assert.equal(scripts[0].src, 'https://accounts.google.com/gsi/client')
  scripts[0].onerror()
  await assert.rejects(first, /Google sign-in couldn’t load/)
  assert.equal(scripts[0].removed, true)
  const retry = loadGoogleSlidesAuth()
  window.google = { accounts: { oauth2: { initTokenClient() {} } } }
  scripts[1].onload()
  await retry
  await loadGoogleSlidesAuth()
  assert.equal(scripts.length, 2)
})

test('starts the Google popup during the click and requests only app-file access', async t => {
  let called = false
  fakeGoogle(t, config => {
    called = true
    assert.equal(config.scope, scope)
    assert.equal(config.include_granted_scopes, false)
    assert.equal(config.client_id, 'example.apps.googleusercontent.com')
    config.callback({ access_token: 'test-token', scope })
  })
  const authorization = authorizeGoogleSlides('example.apps.googleusercontent.com')
  assert.equal(called, true)
  assert.equal(await authorization, 'test-token')
})

test('reports cancellation, blocked popups, denied and missing file access separately', async t => {
  let invoke
  fakeGoogle(t, config => invoke(config))
  for (const [handler, input, expected] of [
    ['error_callback', { type: 'popup_closed' }, { name: 'AbortError' }],
    ['error_callback', { type: 'popup_failed_to_open' }, /Allow the Google sign-in popup/],
    ['callback', { error: 'access_denied' }, /permission was declined/],
    ['callback', { access_token: 'test-token', scope: 'openid' }, /couldn’t authorize/],
  ]) {
    invoke = config => config[handler](input)
    await assert.rejects(authorizeGoogleSlides('client'), expected)
  }
})

test('sends the original PPTX bytes and target Google Slides MIME type in one Drive create', async t => {
  const bytes = Buffer.from([80, 75, 3, 4, 255, 0, 128])
  const signal = new AbortController().signal
  const upload = t.mock.method(globalThis, 'fetch', async (url, request) => {
    assert.equal(url, 'https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,mimeType&ignoreDefaultVisibility=true')
    assert.equal(request.method, 'POST')
    assert.equal(request.credentials, 'omit')
    assert.equal(request.redirect, 'error')
    assert.equal(request.signal, signal)
    assert.equal(request.headers.Authorization, 'Bearer test-token')
    const boundary = request.headers['Content-Type'].match(/^multipart\/related; boundary=(.+)$/)[1]
    const expected = Buffer.concat([
      Buffer.from('--' + boundary + '\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n' +
        JSON.stringify({ name: 'École “North”', mimeType: nativeMime }) +
        '\r\n--' + boundary + '\r\nContent-Type: ' + sourceMime + '\r\n\r\n'),
      bytes,
      Buffer.from('\r\n--' + boundary + '--\r\n'),
    ])
    assert.deepEqual(Buffer.from(await request.body.arrayBuffer()), expected)
    return Response.json({ id: 'Ab456_-', mimeType: nativeMime })
  })
  const link = await createGoogleSlidesFile({ file: new Blob([bytes]), filename: 'École “North”.pptx', accessToken: 'test-token', signal })
  assert.equal(upload.mock.callCount(), 1)
  assert.equal(link, 'https://docs.google.com/presentation/d/Ab456_-/edit')
})

test('rejects failed, ambiguous or non-native uploads without retrying them', async t => {
  const args = { file: new Blob(['slides']), filename: 'assembly.pptx', accessToken: 'test-token' }
  let respond
  const upload = t.mock.method(globalThis, 'fetch', () => respond())
  for (const [scenario, expected] of [
    [() => new Response('', { status: 401 }), /expired/],
    [() => new Response('', { status: 403 }), /selected account/],
    [() => new Response('', { status: 503 }), /Check Google Drive/],
    [() => { throw new TypeError('offline') }, /Check Google Drive/],
    [() => Response.json({ id: 'existing', mimeType: sourceMime }), /didn’t return/],
    [() => Response.json({ id: '../untrusted', mimeType: nativeMime }), /didn’t return/],
    [() => { throw new DOMException('Canceled', 'AbortError') }, { name: 'AbortError' }],
  ]) {
    respond = scenario
    const before = upload.mock.callCount()
    await assert.rejects(createGoogleSlidesFile(args), expected)
    assert.equal(upload.mock.callCount(), before + 1)
  }
})
