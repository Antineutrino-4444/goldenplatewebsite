// The old 0.35° every 80ms rotation was capped at 12.5fps. Keep that angular
// speed, but advance on display frames and stop all work when it is not seen.
export function startGlobeAnimation(element, advance, {
  Observer = globalThis.IntersectionObserver,
  requestFrame = globalThis.requestAnimationFrame,
  cancelFrame = globalThis.cancelAnimationFrame,
  documentRef = globalThis.document,
  motion = globalThis.matchMedia?.('(prefers-reduced-motion: reduce)'),
} = {}) {
  let visible = !Observer
  let disposed = false
  let frame = null
  let previous
  const tick = (timestamp) => {
    frame = null
    if (disposed) return
    if (previous !== undefined) {
      // A stalled frame must not produce a large catch-up jump.
      advance(Math.min(100, Math.max(0, timestamp - previous)) * 0.35 / 80)
    }
    previous = timestamp
    frame = requestFrame(tick)
  }
  const update = () => {
    const running = visible && !documentRef?.hidden && !motion?.matches
    if (running && frame === null) frame = requestFrame(tick)
    else if (!running) {
      if (frame !== null) cancelFrame(frame)
      frame = null
      previous = undefined
    }
  }
  const observer = Observer && new Observer(([entry]) => {
    if (disposed) return
    visible = entry.isIntersecting
    update()
  })
  observer?.observe(element)
  documentRef?.addEventListener('visibilitychange', update)
  motion?.addEventListener('change', update)
  update()
  return () => {
    disposed = true
    if (frame !== null) cancelFrame(frame)
    observer?.disconnect()
    documentRef?.removeEventListener('visibilitychange', update)
    motion?.removeEventListener('change', update)
  }
}
