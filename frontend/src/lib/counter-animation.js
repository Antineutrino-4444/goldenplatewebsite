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
  const marks = [0, 25, 50, 75, 100]
  // Delayed Fibonacci: add the mark three places back, rather than the
  // immediately preceding one. Growth is gentler (~1.47× rather than ~1.62×).
  // These absolute marks never change when the continuous ruler expands.
  while (true) {
    const next = marks.at(-1) + marks.at(-3)
    if (next >= scale || !Number.isFinite(next)) break
    marks.push(next)
  }
  const ticks = marks.map(value => ({ value, position: position(value) }))
  if (ticks.at(-1).value !== scale) ticks.push({ value: scale, position: 100, endpoint: true })
  return { scale, width: position(count), ticks }
}

const compactScaleNumber = new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 })
const rulerRowHeight = 12
export function communityRulerLabels(ticks, width) {
  const labels = ticks.map((tick) => {
    const text = tick.value < 1000 ? String(tick.value) : compactScaleNumber.format(tick.value)
    const size = text.length * 7 + 2
    const x = tick.position / 100 * width
    const left = Math.max(0, Math.min(width - size, x - size / 2))
    return { ...tick, text, size, x, left, offset: left - x, row: 0, showLabel: true }
  })
  // As the scale grows its moving endpoint can sit directly beside the last
  // fixed mark. Keep both on the first line if the inner label can slide left.
  const endpoint = labels.at(-1)
  const neighbour = labels.at(-2)
  const previous = labels.at(-3)
  if (endpoint?.endpoint && neighbour && previous) {
    const adjusted = Math.min(neighbour.left, endpoint.left - neighbour.size - 3)
    if (adjusted >= previous.left + previous.size + 3) {
      neighbour.left = adjusted
      neighbour.offset = adjusted - neighbour.x
    }
  }
  const rowEnds = []
  for (const tick of [...labels].sort((a, b) => a.left - b.left)) {
    const freeRow = rowEnds.findIndex(end => tick.left >= end + 3)
    tick.row = freeRow < 0 ? rowEnds.length : freeRow
    tick.top = 6 + tick.row * rulerRowHeight
    rowEnds[tick.row] = tick.left + tick.size
  }
  return { ticks: labels, height: Math.max(30, 6 + rowEnds.length * rulerRowHeight) }
}

export function communityRulerHeight(count, width) {
  const layout = communityBarLayout(count)
  // Marks are closest at the largest saved count. At either edge a label
  // can extend its full width in one direction instead of half its width.
  // Reserve for those overlaps plus the moving endpoint throughout the animation.
  const fixed = layout.ticks.filter(tick => !tick.endpoint)
  const labels = communityRulerLabels(fixed, width).ticks
  let rows = 1
  for (const leading of [.5, 1]) {
    const intervals = labels.map(({ x, size }) => ({
      start: x - leading * size, end: x + (1.5 - leading) * size + 3,
    }))
    for (const { start } of intervals) {
      const overlaps = intervals.filter(other => other.start <= start && other.end > start)
      rows = Math.max(rows, overlaps.length)
    }
  }
  return count ? Math.max(30, 6 + (rows + 1) * rulerRowHeight) : 30
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
