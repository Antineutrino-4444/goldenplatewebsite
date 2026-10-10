import test from 'node:test'
import assert from 'node:assert/strict'
import { startCounterPolling, rangeLabel, COUNTER_REFRESH_MS } from '../src/lib/live-counter.js'

const flush = async () => { await Promise.resolve(); await Promise.resolve() }
function timers() {
  const queued = new Map()
  let id = 0
  return {
    queued,
    schedule(callback, delay) { const key = ++id; queued.set(key, { callback, delay }); return key },
    cancel(key) { queued.delete(key) },
    runNext() { const [key, task] = queued.entries().next().value; queued.delete(key); return task.callback() },
  }
}

test('counter loads immediately and keeps updating every five seconds', async () => {
  const clock = timers()
  const results = []
  let count = 0
  const poller = startCounterPolling({ read: async () => ++count, onData: (data) => results.push(data),
    onError: () => assert.fail('unexpected error'), ...clock })
  await flush()
  assert.deepEqual(results, [1])
  assert.equal([...clock.queued.values()][0].delay, COUNTER_REFRESH_MS)
  await clock.runNext()
  assert.deepEqual(results, [1, 2])
  poller.stop()
  assert.equal(clock.queued.size, 0)
})

test('temporary connection errors retry and recover automatically', async () => {
  const clock = timers()
  const results = []
  const errors = []
  let calls = 0
  const poller = startCounterPolling({ read: async () => {
    if (++calls === 1) throw new Error('offline')
    return 10
  }, onData: (data) => results.push(data), onError: (error) => errors.push(error.message), ...clock })
  await flush()
  assert.deepEqual(errors, ['offline'])
  await clock.runNext()
  assert.deepEqual(results, [10])
  poller.stop()
})

test('slow requests never overlap and leaving aborts stale results', async () => {
  const clock = timers()
  let complete
  let signal
  let calls = 0
  const results = []
  const poller = startCounterPolling({ read: (requestSignal) => {
    signal = requestSignal
    calls++
    return new Promise((resolve) => { complete = resolve })
  }, onData: (data) => results.push(data), onError: () => assert.fail('unexpected error'), ...clock })
  await poller.refresh()
  await poller.refresh()
  assert.equal(calls, 1)
  complete(3)
  await flush()
  assert.equal([...clock.queued.values()][0].delay, 0)
  clock.runNext()
  assert.equal(calls, 2)
  poller.stop()
  assert.equal(signal.aborted, true)
  complete(99)
  await flush()
  assert.deepEqual(results, [3])
  assert.equal(clock.queued.size, 0)
})

test('optional names use the dates when blank', () => {
  const range = { start_date: '2026-10-10', end_date: '2026-10-11' }
  assert.equal(rangeLabel({ ...range, name: ' Fall term ' }), 'Fall term')
  assert.match(rangeLabel({ ...range, name: '  ' }), /2026/)
  assert.ok(!rangeLabel(range).includes('Invalid'))
})
