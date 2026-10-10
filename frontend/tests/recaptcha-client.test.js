import assert from 'node:assert/strict'
import test from 'node:test'
import { createRecaptchaClient, RecaptchaError } from '../src/lib/recaptcha-client.js'

function harness(options = {}) {
  const scripts = []
  const calls = []
  const fakeWindow = {
    grecaptcha: {
      ready(callback) { callback() },
      execute(key, { action }) {
        calls.push({ key, action })
        return Promise.resolve(`token-${calls.length}`)
      },
    },
  }
  const fakeDocument = {
    createElement(tag) {
      assert.equal(tag, 'script')
      return { remove() { this.removed = true } }
    },
    head: { appendChild(script) { scripts.push(script) } },
  }
  const client = createRecaptchaClient('public-test-key', {
    getWindow: () => fakeWindow, getDocument: () => fakeDocument,
    timeoutMs: 50, ...options,
  })
  return { client, scripts, calls, fakeWindow }
}

test('shared loader executes fresh tokens for each action, including concurrent requests', async () => {
  const { client, scripts, calls } = harness()
  const first = client.getToken('account_signup')
  const second = client.getToken('school_email_code')
  assert.equal(scripts.length, 1)
  assert.equal(scripts[0].src, 'https://www.google.com/recaptcha/api.js?render=public-test-key')
  scripts[0].onload()
  assert.deepEqual(await Promise.all([first, second]), ['token-1', 'token-2'])
  assert.equal(await client.getToken('map_submit'), 'token-3')
  assert.deepEqual(calls.map((call) => call.action), ['account_signup', 'school_email_code', 'map_submit'])
  assert.equal(scripts.length, 1)
})

test('unconfigured development does not load Google or invent a token', async () => {
  const client = createRecaptchaClient('', { getDocument: () => { throw new Error('must not load') } })
  assert.equal(await client.getToken('account_signup'), null)
})

test('script failure is recoverable with a new script and token', async () => {
  const { client, scripts } = harness()
  const first = client.getToken('map_submit')
  scripts[0].onerror()
  await assert.rejects(first, RecaptchaError)
  assert.equal(scripts[0].removed, true)
  const retry = client.getToken('map_submit')
  assert.equal(scripts.length, 2)
  scripts[1].onload()
  assert.equal(await retry, 'token-1')
})

test('script or ready timeout does not hang the form and permits retry', async () => {
  const { client, scripts, fakeWindow } = harness({ timeoutMs: 5 })
  fakeWindow.grecaptcha.ready = () => {}
  const first = client.getToken('school_register')
  scripts[0].onload()
  await assert.rejects(first, RecaptchaError)
  fakeWindow.grecaptcha.ready = (callback) => callback()
  const retry = client.getToken('school_register')
  scripts[1].onload()
  assert.equal(await retry, 'token-1')
})

test('missing Google API rejects verification and permits recovery', async () => {
  const { client, scripts, fakeWindow } = harness()
  const api = fakeWindow.grecaptcha
  fakeWindow.grecaptcha = undefined
  const first = client.getToken('map_email_code')
  scripts[0].onload()
  await assert.rejects(first, RecaptchaError)
  fakeWindow.grecaptcha = api
  const retry = client.getToken('map_email_code')
  scripts[1].onload()
  assert.equal(await retry, 'token-1')
})

test('execute timeout allows a later fresh execution', async () => {
  const { client, scripts, fakeWindow } = harness({ timeoutMs: 5 })
  const execute = fakeWindow.grecaptcha.execute
  fakeWindow.grecaptcha.execute = () => new Promise(() => {})
  const first = client.getToken('map_submit')
  scripts[0].onload()
  await assert.rejects(first, RecaptchaError)
  fakeWindow.grecaptcha.execute = execute
  assert.equal(await client.getToken('map_submit'), 'token-1')
})

for (const invalid of ['', null, 123]) {
  test(`invalid token ${JSON.stringify(invalid)} never passes verification`, async () => {
    const { client, scripts, fakeWindow } = harness()
    fakeWindow.grecaptcha.execute = async () => invalid
    const pending = client.getToken('account_signup')
    scripts[0].onload()
    await assert.rejects(pending, RecaptchaError)
  })
}

test('Google execution failure can be retried without reloading the page', async () => {
  const { client, scripts, fakeWindow } = harness()
  const execute = fakeWindow.grecaptcha.execute
  fakeWindow.grecaptcha.execute = () => { throw new Error('Google unavailable') }
  const pending = client.getToken('account_signup')
  scripts[0].onload()
  await assert.rejects(pending, RecaptchaError)
  fakeWindow.grecaptcha.execute = execute
  assert.equal(await client.getToken('account_signup'), 'token-1')
})
