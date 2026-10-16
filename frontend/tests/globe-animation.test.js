import test from 'node:test'
import assert from 'node:assert/strict'
import { startGlobeAnimation } from '../src/lib/globe-animation.js'

function scene({ reduced = false, ObserverEnabled = true } = {}) {
  const documentRef = new EventTarget(), motion = new EventTarget()
  documentRef.hidden = false
  motion.matches = reduced
  const frames = new Map(), changes = [], observers = []
  let serial = 0
  class Observer {
    constructor(callback) { this.callback = callback; observers.push(this) }
    observe(element) { this.element = element }
    disconnect() { this.disconnected = true }
    emit(visible) { this.callback([{ isIntersecting: visible }]) }
  }
  const stop = startGlobeAnimation({}, degrees => changes.push(degrees), {
    Observer: ObserverEnabled ? Observer : null, documentRef, motion,
    requestFrame: callback => { const id = serial++; frames.set(id, callback); return id },
    cancelFrame: id => frames.delete(id),
  })
  return { documentRef, motion, frames, changes, observers, stop,
    step(timestamp) { const pending = [...frames.values()]; frames.clear(); pending.forEach(callback => callback(timestamp)) },
    total() { return changes.reduce((sum, value) => sum + value, 0) },
  }
}

test('globe advances at the same angular speed on 60Hz and 120Hz displays', () => {
  for (const rate of [60, 120]) {
    const globe = scene()
    assert.equal(globe.frames.size, 0, 'no frames before the globe enters the viewport')
    globe.observers[0].emit(true)
    for (let frame = 0; frame <= rate; frame++) globe.step(frame * 1000 / rate)
    assert.equal(globe.changes.length, rate)
    assert.ok(Math.abs(globe.total() - 4.375) < .00001)
    assert.ok(globe.changes.every(degrees => degrees < .08), 'small per-frame steps replace the old 0.35° jumps')
    globe.stop()
    assert.equal(globe.frames.size, 0)
  }
})

test('offscreen and background globes do no frame work and resume without catching up', () => {
  const globe = scene()
  globe.observers[0].emit(true)
  globe.step(0); globe.step(16)
  const before = globe.total()
  globe.observers[0].emit(false)
  assert.equal(globe.frames.size, 0)
  globe.observers[0].emit(true)
  globe.step(10000)
  assert.equal(globe.total(), before)
  globe.documentRef.hidden = true
  globe.documentRef.dispatchEvent(new Event('visibilitychange'))
  assert.equal(globe.frames.size, 0)
  globe.documentRef.hidden = false
  globe.documentRef.dispatchEvent(new Event('visibilitychange'))
  globe.step(20000); globe.step(20016)
  assert.ok(Math.abs(globe.total() - before * 2) < .00001)
  globe.stop()
  assert.equal(globe.observers[0].disconnected, true)
})

test('reduced-motion changes stop/resume rotation and cleanup rejects late frames', () => {
  const globe = scene({ reduced: true, ObserverEnabled: false })
  assert.equal(globe.frames.size, 0)
  globe.motion.matches = false
  globe.motion.dispatchEvent(new Event('change'))
  globe.step(0); globe.step(16)
  globe.motion.matches = true
  globe.motion.dispatchEvent(new Event('change'))
  assert.equal(globe.frames.size, 0)
  globe.motion.matches = false
  globe.motion.dispatchEvent(new Event('change'))
  const late = [...globe.frames.values()][0]
  const before = globe.total()
  globe.stop()
  late(50000)
  assert.equal(globe.frames.size, 0)
  assert.equal(globe.total(), before)
})

test('one stalled frame cannot cause a large globe jump', () => {
  const globe = scene({ ObserverEnabled: false })
  globe.step(0); globe.step(10000)
  assert.ok(globe.total() <= .4375)
  globe.stop()
})
