import test from 'node:test'
import assert from 'node:assert/strict'
import { counterAnimationValue, crossedMilestone, counterBarLayout, communityBarLayout, communityRulerLabels } from '../src/lib/counter-animation.js'

test('count starts slowly, accelerates through the middle, and finishes slowly at the exact total', () => {
  const values = [0, 0.25, 0.5, 0.75, 1].map((progress) => counterAnimationValue(0, 10000, progress))
  assert.equal(values[0], 0)
  assert.equal(values[4], 10000)
  const increments = values.slice(1).map((value, index) => value - values[index])
  assert.ok(increments[0] < increments[1])
  assert.ok(increments[3] < increments[2])
  assert.equal(values[2], 5000)
  assert.equal(counterAnimationValue(0, 10000, -1), 0)
  assert.equal(counterAnimationValue(0, 10000, 2), 10000)
})

test('community bar grows without a goal and compresses its ruler as totals increase', () => {
  let previous = communityBarLayout(0)
  assert.equal(previous.width, 0)
  for (const count of [1, 10, 100, 1000, 10000, 1000000, 1000000000]) {
    const layout = communityBarLayout(count)
    assert.ok(layout.width > previous.width && layout.width < 100)
    assert.ok(layout.scale > previous.scale && layout.scale > count)
    assert.equal(layout.ticks[0].value, 0)
    assert.equal(layout.ticks.at(-1).value, layout.scale)
    assert.ok(layout.ticks.every((tick) => tick.position >= 0 && tick.position <= 100))
    previous = layout
  }
  assert.deepEqual(communityBarLayout(-1), communityBarLayout(0))
})

test('live count transitions can increase or decrease without overshooting', () => {
  assert.equal(counterAnimationValue(120, 150, 1), 150)
  assert.equal(counterAnimationValue(150, 120, 1), 120)
  assert.ok(counterAnimationValue(150, 120, 0.5) >= 120)
})

test('old ruler marks remain and compress left as new scales accumulate', () => {
  let previous = communityBarLayout(0)
  for (const count of [100, 1000, 10000, 1000000, 1000000000]) {
    const next = communityBarLayout(count)
    for (const mark of previous.ticks.filter(tick => !tick.endpoint)) {
      const retained = next.ticks.find(tick => tick.value === mark.value)
      assert.ok(retained, `${mark.value} must remain on the expanded ruler`)
      if (mark.value > 0) assert.ok(retained.position < mark.position)
    }
    previous = next
  }
})

test('logarithmic fill uses the same coordinates as the ruler', () => {
  const layout = communityBarLayout(1025)
  assert.equal(layout.width, layout.ticks.find(tick => tick.value === 1025).position)
  const zeroTo100 = layout.ticks.find(tick => tick.value === 100).position
  const hundredTo1000 = layout.width - zeroTo100
  assert.ok(hundredTo1000 > zeroTo100, 'larger ranges have space without losing the original scale')
})

test('crowded phone labels overlap on one baseline without changing ruler height', () => {
  for (const width of [280, 350, 728, 1344]) {
    for (const count of [0, 1, 2800, 1000000, 1000000000]) {
      const ruler = communityRulerLabels(communityBarLayout(count).ticks, width)
      assert.equal(ruler.height, 30)
      assert.ok(ruler.ticks.every(tick => tick.showLabel && tick.row === 0))
      assert.ok(ruler.ticks.every(tick => tick.left >= 0 && tick.left + tick.size <= width))
    }
  }
  const labels = communityRulerLabels(communityBarLayout(1000000).ticks, 350).ticks
  assert.ok(labels.some((tick, index) => index > 0 && tick.left < labels[index - 1].left + labels[index - 1].size),
    'crowding is intentionally retained rather than staggered or hidden')
})

test('scale marks accumulate with gentler growth than adjacent-term Fibonacci', () => {
  const marks = communityBarLayout(1000000).ticks.filter(tick => !tick.endpoint).map(tick => tick.value)
  assert.deepEqual(marks.slice(0, 12), [0, 25, 50, 75, 100, 150, 225, 325, 475, 700, 1025, 1500])
  for (let i = 5; i < marks.length; i++) {
    assert.ok(marks[i] > marks[i - 1])
    assert.ok(marks[i] < marks[i - 1] + marks[i - 2], 'each step grows less than an adjacent-term Fibonacci step')
  }
  for (const count of [149, 150, 151, 1024, 1025, 1026]) {
    const a = communityBarLayout(count), b = communityBarLayout(count + 0.001)
    assert.ok(Math.abs(a.width - b.width) < .001, 'adding a mark does not jump the fill')
    for (const mark of a.ticks.filter(tick => !tick.endpoint)) {
      assert.ok(Math.abs(mark.position - b.ticks.find(tick => tick.value === mark.value).position) < .001)
    }
  }
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
