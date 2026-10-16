export function guestPageScope(pathname) {
  const path = pathname.replace(/\/+$/, '') || '/'
  if (path === '/portal' || path.startsWith('/portal/')) return 'portal'
  if (path.startsWith('/guest/schools/')) return 'entry'
  if (path === '/live-counter') return 'counter'
  return null
}

export function shouldEndGuestSession(previousPath, nextPath) {
  const next = guestPageScope(nextPath)
  if (previousPath === null) return next !== 'portal' && next !== 'entry'
  const previous = guestPageScope(previousPath)
  // A successful guest login enters the portal without ending its new session.
  if (previous === 'entry' && next === 'portal') return false
  if (previous === next) return false
  return previous !== null || ['/login', '/signup', '/register'].includes(nextPath)
}

// Serialize guest entry and exit so an unfinished pin/login request cannot
// recreate guest access after the visitor has already left its page.
export function createGuestSessionManager(request = (...args) => fetch(...args)) {
  let tail = Promise.resolve()
  let exit = null
  const enqueue = (operation) => {
    const result = tail.then(operation, operation)
    tail = result.catch(() => {})
    return result
  }
  return {
    enter(payload, initialize) {
      exit = null
      return enqueue(async () => {
        const controller = new AbortController()
        const timeout = setTimeout(() => controller.abort(), 10000)
        try {
          const response = await request('/api/auth/guest', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload), signal: controller.signal,
          })
          return initialize ? await initialize(response) : response
        } finally { clearTimeout(timeout) }
      })
    },
    leave() {
      if (exit) return exit
      exit = enqueue(async () => {
        const controller = new AbortController()
        const timeout = setTimeout(() => controller.abort(), 8000)
        try {
          const response = await request('/api/auth/guest/logout', {
            method: 'POST', signal: controller.signal, keepalive: true,
          })
          return response.ok
        } catch { return false }
        finally { clearTimeout(timeout) }
      })
      const current = exit
      current.finally(() => { if (exit === current) exit = null })
      return current
    },
  }
}

export const guestSession = createGuestSessionManager()
