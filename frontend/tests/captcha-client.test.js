import assert from 'node:assert/strict'
import test from 'node:test'
import { createCaptchaClient, CaptchaError } from '../src/lib/captcha-client.js'

const actions = ['account_signup', 'account_email_code', 'school_register', 'school_email_code', 'map_submit', 'map_email_code', 'password_recovery']

function element() {
  return {
    isConnected: true, clientWidth: 320, children: [],
    appendChild(child) { this.children.push(child); child.parent = this },
    remove() { this.removed = true; if (this.parent) this.parent.children = this.parent.children.filter((child) => child !== this) },
    scrollIntoView() { this.scrolled = true },
  }
}

function harness(options = {}) {
  const scripts = []
  const widgets = []
  const calls = []
  const removed = []
  const fakeWindow = {
    turnstile: {
      render(host, config) {
        const id = `widget-${widgets.length}`
        widgets.push({ id, host, config })
        return id
      },
      execute(id) {
        const widget = widgets.find((widget) => widget.id === id)
        calls.push(widget)
        queueMicrotask(() => widget.config.callback(`token-${id}`))
      },
      remove(id) { removed.push(id) },
    },
  }
  const fakeDocument = {
    createElement(tag) { assert.ok(['script', 'div'].includes(tag)); return element() },
    head: { appendChild(script) { scripts.push(script) } },
  }
  const client = createCaptchaClient('public-test-key', {
    getWindow: () => fakeWindow, getDocument: () => fakeDocument,
    timeoutMs: 50, challengeTimeoutMs: 50, ...options,
  })
  const container = element()
  const unregister = client.registerContainer(container, actions)
  return { client, container, unregister, scripts, widgets, calls, removed, fakeWindow }
}

async function ready(h) {
  const loading = h.client.load()
  h.scripts.at(-1).onload()
  await loading
}

test('shared script, fresh action-bound tokens and no reusable widget after success', async () => {
  const h = harness()
  const school = element()
  h.client.registerContainer(school, ['school_email_code'])
  const first = h.client.getToken('account_signup')
  const second = h.client.getToken('school_email_code')
  assert.equal(h.scripts.length, 1)
  assert.equal(h.scripts[0].src, 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit')
  h.scripts[0].onload()
  assert.deepEqual(await Promise.all([first, second]), ['token-widget-0', 'token-widget-1'])
  assert.equal(await h.client.getToken('map_submit'), 'token-widget-2')
  assert.deepEqual(h.calls.map(({ config }) => config.action), ['account_signup', 'school_email_code', 'map_submit'])
  assert.equal(h.scripts.length, 1)
  assert.equal(h.removed.length, 3)
  assert.equal(h.container.children.length, 0)
  assert.equal(school.children.length, 0)
})

test('unconfigured development loads no provider script or invented token', async () => {
  const client = createCaptchaClient('', { getDocument: () => { throw new Error('must not load') } })
  assert.equal(await client.getToken('account_signup'), null)
})

test('each action must have a mounted matching form', async () => {
  const h = harness()
  await assert.rejects(h.client.getToken('unregistered_action'), CaptchaError)
  assert.equal(h.scripts.length, 0)
})

test('script failure removes the failed script and allows retry', async () => {
  const h = harness()
  const first = h.client.getToken('map_submit')
  h.scripts[0].onerror()
  await assert.rejects(first, CaptchaError)
  assert.equal(h.scripts[0].removed, true)
  const retry = h.client.getToken('map_submit')
  h.scripts[1].onload()
  assert.equal(await retry, 'token-widget-0')
})

test('script timeout allows a new load', async () => {
  const h = harness({ timeoutMs: 5 })
  await assert.rejects(h.client.getToken('school_register'), CaptchaError)
  const retry = h.client.getToken('school_register')
  h.scripts[1].onload()
  assert.equal(await retry, 'token-widget-0')
})

test('missing provider API rejects loading and allows recovery', async () => {
  const h = harness()
  const api = h.fakeWindow.turnstile
  h.fakeWindow.turnstile = undefined
  const first = h.client.getToken('map_email_code')
  h.scripts[0].onload()
  await assert.rejects(first, CaptchaError)
  h.fakeWindow.turnstile = api
  const retry = h.client.getToken('map_email_code')
  h.scripts[1].onload()
  assert.equal(await retry, 'token-widget-0')
})

test('challenge timeout removes the widget and a late callback cannot satisfy the next request', async () => {
  const h = harness({ challengeTimeoutMs: 5 })
  h.fakeWindow.turnstile.execute = () => {}
  await ready(h)
  await assert.rejects(h.client.getToken('map_submit'), CaptchaError)
  assert.deepEqual(h.removed, ['widget-0'])
  const retry = h.client.getToken('map_submit')
  await Promise.resolve()
  h.widgets[0].config.callback('stale-token')
  h.widgets[1].config.callback('fresh-token')
  assert.equal(await retry, 'fresh-token')
})

for (const invalid of ['', '   ', null, 123, 'x'.repeat(2049)]) {
  test(`invalid token (${typeof invalid}, length ${invalid?.length ?? 'n/a'}) is rejected`, async () => {
    const h = harness()
    h.fakeWindow.turnstile.execute = (id) => h.widgets.find((widget) => widget.id === id).config.callback(invalid)
    await ready(h)
    await assert.rejects(h.client.getToken('account_signup'), CaptchaError)
    assert.equal(h.removed.length, 1)
  })
}

for (const callback of ['error-callback', 'expired-callback', 'timeout-callback']) {
  test(`${callback} releases the form for a fresh retry`, async () => {
    const h = harness()
    const execute = h.fakeWindow.turnstile.execute
    h.fakeWindow.turnstile.execute = (id) => h.widgets.find((widget) => widget.id === id).config[callback]()
    await ready(h)
    await assert.rejects(h.client.getToken('account_signup'), CaptchaError)
    h.fakeWindow.turnstile.execute = execute
    assert.equal(await h.client.getToken('account_signup'), 'token-widget-1')
  })
}

test('unmount cancels a challenge, removes its widget, and does not reuse a replacement form', async () => {
  const h = harness()
  h.fakeWindow.turnstile.execute = () => {}
  await ready(h)
  const request = h.client.getToken('account_signup')
  await Promise.resolve()
  h.unregister()
  await assert.rejects(request, CaptchaError)
  assert.deepEqual(h.removed, ['widget-0'])
  assert.equal(h.container.children.length, 0)
})

test('unmount during script load cannot render into a new registration', async () => {
  const h = harness()
  const request = h.client.getToken('account_signup')
  h.unregister()
  h.client.registerContainer(h.container, actions)
  h.scripts[0].onload()
  await assert.rejects(request, CaptchaError)
  assert.equal(h.widgets.length, 0)
})

test('double submit cannot replace an active challenge in the same form', async () => {
  const h = harness()
  h.fakeWindow.turnstile.execute = () => {}
  await ready(h)
  const first = h.client.getToken('account_signup')
  await Promise.resolve()
  await assert.rejects(h.client.getToken('account_email_code'), CaptchaError)
  h.widgets[0].config.callback('first-token')
  assert.equal(await first, 'first-token')
  assert.equal(h.widgets.length, 1)
})

test('managed challenge stays inside the form, scrolls into view and fits narrow dialogs', async () => {
  const h = harness()
  h.container.clientWidth = 250
  h.fakeWindow.turnstile.execute = () => {}
  await ready(h)
  const request = h.client.getToken('account_signup')
  await Promise.resolve()
  const { host, config } = h.widgets[0]
  assert.equal(host.parent, h.container)
  assert.equal(config.size, 'compact')
  assert.equal(config.appearance, 'interaction-only')
  assert.equal(config.execution, 'execute')
  config['before-interactive-callback']()
  assert.equal(h.container.scrolled, true)
  config.callback('token')
  assert.equal(await request, 'token')
})

test('provider render/execute exceptions clean up and allow a new attempt', async () => {
  const h = harness()
  const execute = h.fakeWindow.turnstile.execute
  h.fakeWindow.turnstile.execute = () => { throw new Error('Provider unavailable') }
  await ready(h)
  await assert.rejects(h.client.getToken('account_signup'), CaptchaError)
  h.fakeWindow.turnstile.execute = execute
  assert.equal(await h.client.getToken('account_signup'), 'token-widget-1')
})
