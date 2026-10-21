export class CaptchaError extends Error {
  constructor(message = 'Unable to load verification. Please check your connection and try again.') {
    super(message)
    this.name = 'CaptchaError'
  }
}

// One script per page; a fresh widget/token for each protected request.
export function createCaptchaClient(siteKey, {
  getWindow = () => window, getDocument = () => document,
  timeoutMs = 15000, challengeTimeoutMs = 120000,
} = {}) {
  let scriptPromise = null
  const containers = new Map()
  const pending = new Map()

  const load = () => {
    if (!siteKey) return Promise.resolve(null)
    if (scriptPromise) return scriptPromise
    scriptPromise = new Promise((resolve, reject) => {
      const script = getDocument().createElement('script')
      let settled = false
      const fail = () => {
        if (settled) return
        settled = true
        clearTimeout(timer)
        script.remove()
        scriptPromise = null
        reject(new CaptchaError())
      }
      const timer = setTimeout(fail, timeoutMs)
      script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit'
      script.async = true
      script.onerror = fail
      script.onload = () => {
        const api = getWindow().turnstile
        if (!['render', 'execute', 'remove'].every((method) => typeof api?.[method] === 'function')) {
          fail()
          return
        }
        settled = true
        clearTimeout(timer)
        resolve(api)
      }
      getDocument().head.appendChild(script)
    })
    return scriptPromise
  }

  const registerContainer = (container, actions) => {
    const registration = { container, actions }
    containers.set(container, registration)
    return () => {
      if (containers.get(container) !== registration) return
      containers.delete(container)
      pending.get(container)?.cancel()
    }
  }

  const getToken = async (action) => {
    if (!siteKey) return null
    // The most recently mounted matching form owns this action. Capture the
    // registration before loading so navigation cannot redirect the request.
    const registration = [...containers.values()].reverse().find(
      ({ container, actions }) => container.isConnected && actions.includes(action),
    )
    if (!registration) throw new CaptchaError('Verification is not ready. Please reopen the form and try again.')
    const { container } = registration
    const api = await load()
    if (containers.get(container) !== registration || !container.isConnected) throw new CaptchaError()
    if (pending.has(container)) throw new CaptchaError('Verification is already running. Please complete the current check.')

    return new Promise((resolve, reject) => {
      let settled = false
      let widgetId
      const host = getDocument().createElement('div')
      container.appendChild(host)
      const finish = (error, token) => {
        if (settled) return
        settled = true
        clearTimeout(timer)
        pending.delete(container)
        // Defer removal until render/execute and their callbacks have returned.
        queueMicrotask(() => {
          try { if (widgetId !== undefined) api.remove(widgetId) } catch { /* The form may already be gone. */ }
          host.remove()
        })
        if (error) reject(error)
        else resolve(token)
      }
      const timer = setTimeout(() => finish(new CaptchaError('Verification timed out. Please try again.')), challengeTimeoutMs)
      pending.set(container, { cancel: () => finish(new CaptchaError('Verification was cancelled. Please try again.')) })
      try {
        widgetId = api.render(host, {
          sitekey: siteKey,
          action,
          execution: 'execute',
          appearance: 'interaction-only',
          theme: 'auto',
          size: container.clientWidth < 300 ? 'compact' : 'flexible',
          'response-field': false,
          retry: 'never',
          callback: (token) => {
            if (typeof token !== 'string' || !token.trim() || token.length > 2048) finish(new CaptchaError())
            else finish(null, token)
          },
          'error-callback': () => finish(new CaptchaError('Verification failed. Please check your connection and try again.')),
          'expired-callback': () => finish(new CaptchaError('Verification expired. Please try again.')),
          'timeout-callback': () => finish(new CaptchaError('Verification timed out. Please try again.')),
          'before-interactive-callback': () => container.scrollIntoView({ block: 'nearest' }),
        })
        if (typeof widgetId !== 'string' || !widgetId) throw new CaptchaError()
        if (!settled) api.execute(widgetId)
      } catch {
        finish(new CaptchaError())
      }
    })
  }

  return { load, registerContainer, getToken }
}
