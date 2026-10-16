export function observeCounterVisibility(element, onChange, {
  Observer = globalThis.IntersectionObserver, viewportHeight = globalThis.innerHeight || 800,
  enterElement = element,
} = {}) {
  if (!Observer) { onChange(true); return () => {} }
  let active = false
  let disposed = false
  const update = (visible) => {
    if (disposed || active === visible) return
    active = visible
    onChange(visible)
  }
  // Start at the ruler, but reset against the entire counter (including its
  // number). A half-screen buffer on BOTH edges keeps resets well out of sight.
  const inset = Math.round(Math.min(96, Math.max(24, viewportHeight * 0.12)))
  const buffer = Math.ceil(Math.max(160, viewportHeight * 0.5))
  const enter = new Observer(([entry]) => {
    if (entry.isIntersecting && entry.intersectionRatio >= 0.75) update(true)
  }, { rootMargin: `-${inset}px 0px -${inset}px 0px`, threshold: 0.75 })
  const exit = new Observer(([entry]) => {
    if (!entry.isIntersecting || entry.intersectionRatio === 0) update(false)
  }, { rootMargin: `${buffer}px 0px ${buffer}px 0px`, threshold: 0 })
  enter.observe(enterElement)
  exit.observe(element)
  return () => { disposed = true; enter.disconnect(); exit.disconnect() }
}
