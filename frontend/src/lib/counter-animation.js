export function counterAnimationValue(from, to, progress) {
  const clamped = Math.min(1, Math.max(0, progress))
  const eased = 1 - (1 - clamped) ** 4
  return Math.round(from + (to - from) * eased)
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
