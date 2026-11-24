export const deckServices = { google: 'Google Slides', microsoft: 'PowerPoint / OneDrive' }

export function deckStatus(deck, now = Date.now()) {
  if (['ready', 'pending', 'retry'].includes(deck.status) && Date.parse(deck.lease_until) > now) return 'Syncing…'
  if (deck.status === 'pending') return 'Update queued'
  return { ready: 'Synced', retry: 'Update failed', reconnect: 'Reconnect required' }[deck.status] || 'Unavailable'
}

export function deckTime(value) {
  const date = new Date(value)
  if (!value || !Number.isFinite(date.getTime())) return 'Not synced yet'
  return date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

export function deckUrl(value) {
  try {
    const url = new URL(value)
    return url.protocol === 'https:' && !url.username && !url.password ? url.href : null
  } catch { return null }
}
