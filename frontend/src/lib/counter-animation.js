export function counterAnimationValue(from, to, progress) {
  const clamped = Math.min(1, Math.max(0, progress))
  // Smooth acceleration and deceleration, with zero velocity at both ends.
  const eased = clamped ** 3 * (clamped * (clamped * 6 - 15) + 10)
  return Math.round(from + (to - from) * eased)
}

export function communityBarLayout(value) {
  const count = Number.isFinite(value) ? Math.max(0, value) : 0
  // A growing logarithmic ruler, without a goal. Keep the original 0–100
  // marks and add larger ranges; old marks compress left rather than vanish.
  const scale = Math.ceil(100 + count * Math.E)
  const position = (mark) => Math.log1p(mark / 100) / Math.log1p(scale / 100) * 100
  const marks = new Set([0, 25, 50, 75, 100])
  for (let unit = 100; unit < scale; unit *= 10) {
    for (const factor of [2.5, 5, 7.5, 10]) if (unit * factor < scale) marks.add(unit * factor)
  }
  const ticks = [...marks].sort((a, b) => a - b).map(value => ({ value, position: position(value) }))
  if (ticks.at(-1).value !== scale) ticks.push({ value: scale, position: 100, endpoint: true })
  return { scale, width: position(count), ticks }
}

const compactScaleNumber = new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 })
export function communityRulerLabels(ticks, width) {
  const rows = [[]]
  const labels = ticks.map((tick) => {
    const text = tick.value < 1000 ? String(tick.value) : compactScaleNumber.format(tick.value)
    const size = text.length * 6.5 + 4
    const x = tick.position / 100 * width
    const left = Math.max(0, Math.min(width - size, x - size / 2))
    return { ...tick, text, size, x, left, offset: left - x, row: 0, showLabel: true }
  })
  // Reserve the two ends, then stack close labels below one another.
  for (const tick of [labels[0], labels.at(-1)]) rows[0].push([tick.left, tick.left + tick.size])
  for (const tick of labels.slice(1, -1)) {
    const fits = row => row.every(([start, end]) => tick.left > end + 7 || tick.left + tick.size + 7 < start)
    let row = rows.findIndex(fits)
    if (row === -1 && (rows.length < 4 || tick.value <= 100)) { row = rows.length; rows.push([]) }
    if (row === -1) tick.showLabel = false // The compressed tick itself always stays.
    else { tick.row = row; rows[row].push([tick.left, tick.left + tick.size]) }
  }
  return { ticks: labels, height: 14 + rows.length * 16 }
}

export function crossedMilestone(previous, next, milestone) {
  return Number.isInteger(milestone) && milestone > 0 && previous < milestone && next >= milestone
}

export function counterBarLayout(count, milestone, total) {
  const scale = Math.max(milestone || total, milestone ? count : 0)
  return {
    scale,
    goalWidth: scale ? Math.min(count, milestone || total) / scale * 100 : 0,
    extraWidth: milestone && count > milestone ? (count - milestone) / scale * 100 : 0,
  }
}
