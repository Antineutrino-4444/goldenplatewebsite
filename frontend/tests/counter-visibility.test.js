import test from 'node:test'
import assert from 'node:assert/strict'
import { observeCounterVisibility } from '../src/lib/counter-visibility.js'

test('counter starts inside the screen, resets completely offscreen, and replays on return', () => {
  const observers = []
  class Observer {
    constructor(callback, options) { this.callback = callback; this.options = options; observers.push(this) }
    observe(element) { this.element = element }
    disconnect() { this.disconnected = true }
    emit(isIntersecting, intersectionRatio) { this.callback([{ isIntersecting, intersectionRatio }]) }
  }
  const states = [], element = {}
  const dispose = observeCounterVisibility(element, value => states.push(value), { Observer, viewportHeight: 844 })
  const [enter, exit] = observers
  assert.equal(enter.options.rootMargin, '-96px 0px -96px 0px')
  assert.equal(enter.element, element)
  enter.emit(true, 0.1)
  assert.deepEqual(states, [], 'a sliver at the edge does not start playback')
  enter.emit(true, 0.8)
  enter.emit(false, 0)
  exit.emit(true, 0.1)
  assert.deepEqual(states, [true], 'moving near an edge does not repeatedly reset')
  exit.emit(false, 0)
  enter.emit(true, 1)
  assert.deepEqual(states, [true, false, true])
  dispose()
  exit.emit(false, 0)
  assert.deepEqual(states, [true, false, true])
  assert.ok(observers.every(observer => observer.disconnected))
})

test('counter remains readable when visibility observation is unavailable', () => {
  const states = []
  const dispose = observeCounterVisibility({}, value => states.push(value), { Observer: null })
  assert.deepEqual(states, [true])
  dispose()
})
