export class RecaptchaError extends Error {
  constructor() {
    super('Unable to load verification. Please check your connection and try again.')
    this.name = 'RecaptchaError'
  }
}

// A single loader per page; each protected request gets a new, single-use token.
export function createRecaptchaClient(siteKey, { getWindow = () => window, getDocument = () => document, timeoutMs = 15000 } = {}) {
  let scriptPromise = null

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
        reject(new RecaptchaError())
      }
      const timer = setTimeout(fail, timeoutMs)
      script.src = `https://www.google.com/recaptcha/api.js?render=${encodeURIComponent(siteKey)}`
      script.async = true
      script.onerror = fail
      script.onload = () => {
        const api = getWindow().grecaptcha
        if (typeof api?.ready !== 'function') { fail(); return }
        try {
          api.ready(() => {
            if (settled) return
            if (typeof api.execute !== 'function') { fail(); return }
            settled = true
            clearTimeout(timer)
            resolve(api)
          })
        } catch { fail() }
      }
      getDocument().head.appendChild(script)
    })
    return scriptPromise
  }

  const getToken = async (action) => {
    const api = await load()
    if (!api) return null
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new RecaptchaError()), timeoutMs)
      Promise.resolve().then(() => api.execute(siteKey, { action }))
        .then((token) => {
          clearTimeout(timer)
          if (typeof token !== 'string' || !token) reject(new RecaptchaError())
          else resolve(token)
        })
        .catch(() => { clearTimeout(timer); reject(new RecaptchaError()) })
    })
  }

  return { load, getToken }
}
