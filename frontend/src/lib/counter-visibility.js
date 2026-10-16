export function observeCounterVisibility(element, onChange, {
  Observer = globalThis.IntersectionObserver, viewportHeight = globalThis.innerHeight || 800,
} = {}) {
  if (!Observer) { onChange(true); return () => {} }
  let active = false
  let disposed = false
  const update = (visible) => {
    if (disposed || active === visible) return
    active = visible
    onChange(visible)
  }
  // Start well inside the viewport, but reset only once the bar fully leaves it.
  // This hysteresis prevents repeated restarts while scrolling around an edge.
  const inset = Math.round(Math.min(96, Math.max(24, viewportHeight * 0.12)))
  const enter = new Observer(([entry]) => {
    if (entry.isIntersecting && entry.intersectionRatio >= 0.75) update(true)
  }, { rootMargin: `-${inset}px 0px -${inset}px 0px`, threshold: 0.75 })
  const exit = new Observer(([entry]) => {
    if (!entry.isIntersecting || entry.intersectionRatio === 0) update(false)
  }, { threshold: 0 })
  enter.observe(element)
  exit.observe(element)
  return () => { disposed = true; enter.disconnect(); exit.disconnect() }
}
