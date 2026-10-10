import test from 'node:test'
import assert from 'node:assert/strict'
import { counterAnimationValue, crossedMilestone } from '../src/lib/counter-animation.js'

test('count rises quickly then slows and finishes exactly at the total', () => {
  const values = [0, 0.25, 0.5, 0.75, 1].map((progress) => counterAnimationValue(0, 10000, progress))
  assert.equal(values[0], 0)
  assert.equal(values[4], 10000)
  const increments = values.slice(1).map((value, index) => value - values[index])
  assert.ok(increments.every((value, index) => index === 0 || value < increments[index - 1]))
  assert.equal(counterAnimationValue(0, 10000, -1), 0)
  assert.equal(counterAnimationValue(0, 10000, 2), 10000)
})

test('live count transitions can increase or decrease without overshooting', () => {
  assert.equal(counterAnimationValue(120, 150, 1), 150)
  assert.equal(counterAnimationValue(150, 120, 1), 120)
  assert.ok(counterAnimationValue(150, 120, 0.5) >= 120)
})

test('celebrate only an upward crossing, including reset and skipped animation values', () => {
  assert.equal(crossedMilestone(0, 150, 100), true)
  assert.equal(crossedMilestone(99, 100, 100), true)
  assert.equal(crossedMilestone(100, 150, 100), false)
  assert.equal(crossedMilestone(150, 150, 100), false)
  assert.equal(crossedMilestone(150, 99, 100), false)
  assert.equal(crossedMilestone(0, 99, 100), false)
  for (const milestone of [null, 0, -1, 1.5, '100']) {
    assert.equal(crossedMilestone(0, 150, milestone), false)
  }
})
