function hasUnsafePathCharacters(value) {
  return [...value].some((character) => character === '\\' || character.codePointAt(0) < 32)
}

export function isMapHost(hostname = '') {
  return hostname.toLowerCase().startsWith('map.')
}

export function isSchoolPortalPath(value) {
  const path = value.split(/[?#]/)[0].replace(/\/+$/, '')
  return ['/portal', '/portal/dashboard', '/portal/admin'].includes(path)
}

// Never allow a login redirect to leave this origin or return to authentication.
export function safeReturnPath(value, fallback = '/portal') {
  if (typeof value !== 'string' || !value.startsWith('/') || value.startsWith('//') || hasUnsafePathCharacters(value)) return fallback
  try {
    const url = new URL(value, 'https://goldenplate.invalid')
    if (url.origin !== 'https://goldenplate.invalid') return fallback
    const path = url.pathname.replace(/\/+$/, '') || '/'
    if (!['/portal', '/portal/dashboard', '/portal/admin', '/map', '/live-counter', '/live-counter/community', '/interschool'].includes(path)) return fallback
    return `${url.pathname}${url.search}${url.hash}`
  } catch { return fallback }
}

export function schoolPortalUrl(location) {
  const url = new URL('/portal', location.href)
  if (isMapHost(url.hostname)) url.hostname = url.hostname.slice(4)
  return url.href
}

export function siteReturnPath(value) {
  if (typeof value !== 'string' || !value.startsWith('/') || value.startsWith('//') || hasUnsafePathCharacters(value)) return '/'
  try {
    const url = new URL(value, 'https://goldenplate.invalid')
    const path = url.pathname.replace(/\/+$/, '') || '/'
    const publicPage = ['/', '/about', '/how-it-works', '/getting-started', '/stories', '/stories/transcript', '/map', '/login', '/register', '/signup', '/live-counter', '/live-counter/community'].includes(path)
    if (url.origin !== 'https://goldenplate.invalid' || (!publicPage && !/^\/guest\/(sessions|schools)\/[a-zA-Z0-9-]+$/.test(path) && safeReturnPath(value, '') === '')) return '/'
    return url.pathname + url.search + url.hash
  } catch { return '/' }
}

export function sitePageLabel(path) {
  const page = path.split(/[?#]/)[0].replace(/\/+$/, '') || '/'
  return ({ '/': 'Home', '/about': 'Our story', '/how-it-works': 'How it works', '/getting-started': 'Getting started', '/stories': 'Watch & listen', '/map': 'School map', '/login': 'School login', '/register': 'School registration', '/signup': 'Account signup', '/live-counter': 'School counter', '/live-counter/community': 'Community counter' })[page]
    || (page === '/stories/transcript' ? 'Podcast transcript' : page.startsWith('/guest/sessions/') ? 'Guest session' : page.startsWith('/guest/schools/') ? 'School guest view' : 'School portal')
}
