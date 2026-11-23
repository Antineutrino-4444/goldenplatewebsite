export const formats = { pptx: 'PowerPoint', 'google-slides': 'Google Slides', pdf: 'PDF' }
export const liveProviders = { pptx: 'microsoft', 'google-slides': 'google' }

export function liveReturnNotice(search) {
  const messages = {
    authorization: 'The cloud account connection was canceled or expired. Connect again to enable updates.',
    access: 'Sign in with an authorized school account to connect this presentation.',
    sync: 'The presentation could not be updated. Try opening it again.',
    config: 'The cloud presentation connection is unavailable. You can still download a copy.',
  }
  const code = new URLSearchParams(search).get('live_error')
  if (!code) return null
  return { type: 'error', message: Object.hasOwn(messages, code) ? messages[code] : 'The cloud connection could not be completed. Please try again.' }
}

export function assemblyAction(format, live, directGoogle, labelChanged = false) {
  if (live.enabled) {
    if (live.link?.status === 'reconnect') return { value: 'live', label: 'Reconnect ' + formats[format] }
    if (live.link && labelChanged) return { value: 'live', label: 'Update live ' + formats[format] + ' deck' }
    if (live.link?.url) return { value: 'live', label: 'Open live ' + formats[format] + ' deck' }
    return { value: 'live', label: (live.link ? 'Check live ' : 'Create live ') + formats[format] + ' deck' }
  }
  if (format === 'google-slides') {
    return directGoogle ? { value: 'google', label: 'Create in Google Slides' } : { value: 'manual', label: 'Prepare for Google Slides' }
  }
  return { value: 'download', label: 'Download ' + formats[format] }
}

export function needsGoogleSlidesNotice(action, format, link) {
  if (format !== 'google-slides') return false
  if (action === 'live') return !link || link.status === 'reconnect'
  return action === 'google' || action === 'manual'
}

export function readPresentationOptions(search) {
  const query = new URLSearchParams(search)
  const format = query.get('format')
  const theme = query.get('theme')
  return {
    kind: 'assembly',
    format: Object.hasOwn(formats, format) ? format : 'pptx',
    linkedTheme: ['light', 'dark'].includes(theme) ? theme : null,
    schoolCode: query.get('school') || '',
    schoolLabel: query.get('school_label'),
  }
}

// Missing leaves an existing live deck's choice alone. A blank value resets it.
export function schoolLabelOption(value) {
  return value == null ? {} : { school_label: value.trim().replace(/\s+/gu, ' ') }
}

export function presentationLoginPath({ format, theme, schoolCode, schoolLabel }) {
  const options = new URLSearchParams({ presentation: 'assembly', theme, format, school: schoolCode.trim() })
  if (schoolLabel != null) options.set('school_label', schoolLabelOption(schoolLabel).school_label)
  const next = '/export?' + options.toString()
  return '/login?' + new URLSearchParams({ next }).toString()
}

export function presentationFileName(disposition, fallback) {
  const encoded = disposition?.match(/filename\*=UTF-8''([^;]+)/i)
  const plain = disposition?.match(/filename="([^"]+)"|filename=([^;\s]+)/i)
  let name = plain?.[1] || plain?.[2] || fallback
  if (encoded) {
    try { name = decodeURIComponent(encoded[1]) } catch { /* Use the plain filename. */ }
  }
  return name.replace(/[\\/]/g, '-')
}
