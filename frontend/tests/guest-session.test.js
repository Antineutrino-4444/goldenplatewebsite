import test from 'node:test'
import assert from 'node:assert/strict'
import { createGuestSessionManager, shouldEndGuestSession } from '../src/lib/guest-session.js'

test('guests stay within portal views and complete entry, then leave on public or auth navigation', () => {
  for (const destination of ['/', '/map', '/signup', '/register', '/login', '/live-counter', '/stories']) {
    assert.equal(shouldEndGuestSession('/portal', destination), true, destination)
  }
  assert.equal(shouldEndGuestSession('/portal', '/portal/dashboard'), false)
  assert.equal(shouldEndGuestSession('/portal/dashboard', '/portal'), false)
  assert.equal(shouldEndGuestSession('/guest/schools/sac', '/portal'), false)
  assert.equal(shouldEndGuestSession('/login', '/portal'), false)
  assert.equal(shouldEndGuestSession('/live-counter', '/register'), true)
  assert.equal(shouldEndGuestSession('/live-counter', '/portal'), true)
  assert.equal(shouldEndGuestSession('/guest/schools/sac', '/map'), true)
})

test('a fresh public visit clears leftover guest cookies before showing auth forms', () => {
  assert.equal(shouldEndGuestSession(null, '/register'), true)
  assert.equal(shouldEndGuestSession(null, '/signup'), true)
  assert.equal(shouldEndGuestSession(null, '/map'), true)
  assert.equal(shouldEndGuestSession(null, '/portal'), false)
  assert.equal(shouldEndGuestSession(null, '/guest/schools/sac'), false)
})

test('leaving waits for an unfinished guest entry and deduplicates concurrent exits', async () => {
  const calls = []
  let finishEntry
  const manager = createGuestSessionManager((url) => {
    calls.push(url)
    return url.endsWith('/guest') ? new Promise(resolve => { finishEntry = resolve }) : Promise.resolve({ ok: true })
  })
  const entering = manager.enter({ school_id: 'sac' })
  await Promise.resolve()
  const leaving = manager.leave()
  assert.equal(manager.leave(), leaving)
  assert.deepEqual(calls, ['/api/auth/guest'])
  finishEntry({ ok: true })
  await entering
  assert.equal(await leaving, true)
  assert.deepEqual(calls, ['/api/auth/guest', '/api/auth/guest/logout'])
})

test('a failed exit remains retryable and a new guest entry waits for exit', async () => {
  let successful = false
  const calls = []
  const manager = createGuestSessionManager(async (url) => {
    calls.push(url)
    if (!successful) throw new Error('offline')
    return { ok: true }
  })
  assert.equal(await manager.leave(), false)
  successful = true
  const leaving = manager.leave()
  const entering = manager.enter({ school_id: 'other-school' })
  assert.equal(await leaving, true)
  await entering
  assert.deepEqual(calls, ['/api/auth/guest/logout', '/api/auth/guest/logout', '/api/auth/guest'])
})

test('exit also waits for session initialization that could update the guest cookie', async () => {
  const calls = []
  let finishInitialization
  const initialized = new Promise(resolve => { finishInitialization = resolve })
  const manager = createGuestSessionManager(async (url) => { calls.push(url); return { ok: true } })
  const entering = manager.enter({ school_id: 'sac' }, async () => {
    await initialized
    return true
  })
  await Promise.resolve()
  const leaving = manager.leave()
  await Promise.resolve()
  assert.deepEqual(calls, ['/api/auth/guest'])
  finishInitialization()
  assert.equal(await entering, true)
  assert.equal(await leaving, true)
  assert.deepEqual(calls, ['/api/auth/guest', '/api/auth/guest/logout'])
})
