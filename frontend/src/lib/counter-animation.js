export function counterAnimationValue(from, to, progress) {
  const clamped = Math.min(1, Math.max(0, progress))
  // Smooth acceleration and deceleration, with zero velocity at both ends.
  const eased = clamped ** 3 * (clamped * (clamped * 6 - 15) + 10)
  return Math.round(from + (to - from) * eased)
}

export function communityBarLayout(value) {
  const count = Number.isFinite(value) ? Math.max(0, value) : 0
  // There is no goal. As counts grow, the visible ruler continuously expands
  // and each plate occupies less space, while the fill keeps moving forward.
  const growth = Math.log1p(count / 100)
  const fraction = growth / (1 + growth)
  const scale = count ? count / fraction : 100
  const unit = 10 ** Math.floor(Math.log10(scale / 4))
  const step = [1, 2, 5, 10].find((factor) => factor * unit >= scale / 4) * unit
  const ticks = [{ value: 0, position: 0 }]
  for (let mark = step; mark < scale; mark += step) {
    const position = mark / scale * 100
    if (position >= 18 && position <= 75 && position - ticks.at(-1).position >= 22) ticks.push({ value: Math.round(mark), position })
  }
  ticks.push({ value: Math.ceil(scale), position: 100 })
  return { scale: Math.ceil(scale), width: fraction * 100, ticks }
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
