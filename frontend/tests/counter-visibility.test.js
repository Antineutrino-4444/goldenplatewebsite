import test from 'node:test'
import assert from 'node:assert/strict'
import { observeCounterVisibility } from '../src/lib/counter-visibility.js'

test('counter starts at the ruler but resets only after the WHOLE counter clears a half-screen buffer', () => {
  const observers = []
  class Observer {
    constructor(callback, options) { this.callback = callback; this.options = options; observers.push(this) }
    observe(element) { this.element = element }
    disconnect() { this.disconnected = true }
    emit(isIntersecting, intersectionRatio) { this.callback([{ isIntersecting, intersectionRatio }]) }
    move(top, bottom) {
      const margin = Number.parseInt(this.options.rootMargin || '0')
      const overlap = Math.max(0, Math.min(bottom, 844 + margin) - Math.max(top, -margin))
      this.emit(overlap > 0, overlap / (bottom - top))
    }
  }
  const states = [], element = {}, bar = {}
  const dispose = observeCounterVisibility(element, value => states.push(value), { Observer, viewportHeight: 844, enterElement: bar })
  const [enter, exit] = observers
  assert.equal(enter.options.rootMargin, '-96px 0px -96px 0px')
  assert.equal(exit.options.rootMargin, '422px 0px 422px 0px')
  assert.equal(enter.element, bar)
  assert.equal(exit.element, element)
  enter.emit(true, 0.1)
  assert.deepEqual(states, [], 'a sliver at the edge does not start playback')
  enter.emit(true, 0.8)
  enter.emit(false, 0)
  exit.emit(true, 0.1)
  assert.deepEqual(states, [true], 'moving near an edge does not repeatedly reset')
  exit.move(-300, -1)
  exit.move(-600, -421)
  exit.move(845, 1145)
  exit.move(1265, 1565)
  assert.deepEqual(states, [true], 'neither viewport edge nor a near-offscreen counter resets the visible number')
  exit.move(-800, -423)
  enter.emit(true, 1)
  exit.move(1267, 1567)
  enter.emit(true, 1)
  assert.deepEqual(states, [true, false, true, false, true], 'both far-offscreen directions reset and replay')
  dispose()
  exit.emit(false, 0)
  assert.deepEqual(states, [true, false, true, false, true])
  assert.ok(observers.every(observer => observer.disconnected))
})

test('counter remains readable when visibility observation is unavailable', () => {
  const states = []
  const dispose = observeCounterVisibility({}, value => states.push(value), { Observer: null })
  assert.deepEqual(states, [true])
  dispose()
})
