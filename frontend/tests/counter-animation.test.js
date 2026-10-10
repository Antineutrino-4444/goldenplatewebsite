import test from 'node:test'
import assert from 'node:assert/strict'
import { counterAnimationValue, crossedMilestone, counterBarLayout } from '../src/lib/counter-animation.js'

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

test('crossing the goal compresses its portion and gives extra plates their own segment', () => {
  assert.deepEqual(counterBarLayout(50, 100, 300), { scale: 100, goalWidth: 50, extraWidth: 0 })
  assert.deepEqual(counterBarLayout(100, 100, 300), { scale: 100, goalWidth: 100, extraWidth: 0 })
  assert.deepEqual(counterBarLayout(125, 100, 300), { scale: 125, goalWidth: 80, extraWidth: 20 })
  assert.deepEqual(counterBarLayout(200, 100, 300), { scale: 200, goalWidth: 50, extraWidth: 50 })
  assert.deepEqual(counterBarLayout(0, null, 0), { scale: 0, goalWidth: 0, extraWidth: 0 })
  assert.deepEqual(counterBarLayout(50, null, 200), { scale: 200, goalWidth: 25, extraWidth: 0 })
})

test('fractional percentage goals compress the bar and celebrate in tenths', () => {
  const layout = counterBarLayout(73.6, 70.1, 100)
  assert.equal(layout.scale, 73.6)
  assert.ok(Math.abs(layout.goalWidth + layout.extraWidth - 100) < 0.000001)
  assert.ok(Math.abs(layout.extraWidth - (3.5 / 73.6 * 100)) < 0.000001)
  assert.equal(crossedMilestone(700, 701, Math.round(70.1 * 10)), true)
  assert.equal(crossedMilestone(701, 736, Math.round(70.1 * 10)), false)
  assert.equal(crossedMilestone(736, 700, Math.round(70.1 * 10)), false)
  assert.deepEqual(counterBarLayout(73.6, null, 100), { scale: 100, goalWidth: 73.6, extraWidth: 0 })
})
