export const COUNTER_REFRESH_MS = 5000

// Poll only after the previous request finishes. Keep retrying after temporary
// failures, and discard any result that arrives after the viewer leaves.
export function startCounterPolling({ read, onData, onError,
  interval = COUNTER_REFRESH_MS, schedule = setTimeout, cancel = clearTimeout }) {
  let stopped = false
  let pending = false
  let refreshQueued = false
  let timer
  let controller
  const refresh = async () => {
    if (stopped) return
    cancel(timer)
    if (pending) {
      refreshQueued = true
      return
    }
    pending = true
    controller = new AbortController()
    try {
      const data = await read(controller.signal)
      if (!stopped) onData(data)
    } catch (error) {
      if (!stopped) onError(error)
    } finally {
      pending = false
      if (!stopped) {
        const delay = refreshQueued ? 0 : interval
        refreshQueued = false
        timer = schedule(refresh, delay)
      }
    }
  }
  refresh()
  return {
    refresh,
    stop() {
      stopped = true
      cancel(timer)
      controller?.abort()
    },
  }
}

export function rangeLabel(range) {
  if (range.name?.trim()) return range.name.trim()
  const formatter = new Intl.DateTimeFormat(undefined, {
    year: 'numeric', month: 'short', day: 'numeric', timeZone: 'UTC',
  })
  return formatter.formatRange(new Date(`${range.start_date}T12:00:00Z`), new Date(`${range.end_date}T12:00:00Z`))
}

export function formatCounterDate(value) {
  return new Date(`${value}T12:00:00Z`).toLocaleDateString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric', timeZone: 'UTC',
  })
}
