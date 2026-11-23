import test from 'node:test'
import assert from 'node:assert/strict'
import { connectGlobeDragging } from '../src/lib/globe-drag.js'

function scene() {
  const svg = new EventTarget()
  svg.dataset = {}
  svg.setPointerCapture = (id) => { svg.captured = id }
  svg.hasPointerCapture = (id) => svg.captured === id
  svg.releasePointerCapture = () => { svg.captured = null }
  const pans = []
  const disconnect = connectGlobeDragging(svg, (dx, dy) => pans.push([dx, dy]))
  function send(type, x = 0, y = 0, extra = {}) {
    const event = Object.assign(new Event(type, { cancelable: true }), {
      pointerId: 1, isPrimary: true, button: 0, clientX: x, clientY: y, detail: 1, ...extra,
    })
    svg.dispatchEvent(event)
    return event
  }
  return { svg, send, pans, disconnect }
}

test('a small movement stays a pin tap; a drag rotates incrementally and consumes its activation', () => {
  const { svg, send, pans, disconnect } = scene()
  send('pointerdown', 10, 20)
  send('pointerup', 12, 21)
  assert.equal(send('click').defaultPrevented, false)
  assert.deepEqual(pans, [])
  send('pointerdown', 10, 20)
  assert.equal(svg.captured, 1)
  send('pointermove', 12, 21)
  send('pointermove', 16, 28)
  send('pointermove', 20, 26)
  assert.equal(svg.dataset.dragging, 'true')
  send('pointerup', 22, 26)
  assert.equal(svg.dataset.dragging, undefined)
  assert.deepEqual(pans, [[6, 8], [4, -2], [2, 0]])
  assert.equal(send('click').defaultPrevented, true)
  send('pointerdown', 22, 26)
  send('pointerup', 22, 26)
  assert.equal(send('click').defaultPrevented, false)
  disconnect()
})

test('touch cancellation, other fingers and keyboard activations do not turn into pin drags', () => {
  const { send, pans, disconnect } = scene()
  send('pointerdown', 0, 0, { button: 2 })
  send('pointermove', 100, 100)
  send('pointerdown', 0, 0)
  send('pointerdown', 20, 20, { pointerId: 2, isPrimary: false })
  send('pointermove', 22, 20, { pointerId: 2, isPrimary: false })
  send('pointermove', 4, -15)
  send('pointercancel')
  send('pointermove', 12, -23)
  assert.deepEqual(pans, [[4, -15]])
  assert.equal(send('click', 0, 0, { detail: 0 }).defaultPrevented, false)
  disconnect()
})

test('unmount releases capture and removes drag listeners', () => {
  const { send, svg, pans, disconnect } = scene()
  send('pointerdown')
  assert.equal(svg.captured, 1)
  disconnect()
  assert.equal(svg.captured, null)
  send('pointermove', 10, 20)
  assert.deepEqual(pans, [])
})
