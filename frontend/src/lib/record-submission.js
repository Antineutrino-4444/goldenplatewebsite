import { formatApiError } from './api-errors.js'

const UNCONFIRMED_SAVE = 'Could not confirm whether the plate was saved. Check Plate Tracking History before trying again.'

// A lost response can follow a successful save. Never describe it as a rejection.
export async function submitRecordRequest(category, payload, fetcher = fetch) {
  let response
  let data
  try {
    response = await fetcher(`/api/record/${encodeURIComponent(category)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
  } catch {
    throw new Error(formatApiError(UNCONFIRMED_SAVE, null, 'RECORD_NETWORK_ERROR'))
  }
  const fallbackCode = response.status >= 400 ? `RECORD_HTTP_${response.status}` : undefined
  try {
    data = await response.json()
  } catch {
    throw new Error(formatApiError(UNCONFIRMED_SAVE, null, fallbackCode || 'RECORD_RESPONSE_INVALID'))
  }
  if (!data || typeof data !== 'object') {
    throw new Error(formatApiError(UNCONFIRMED_SAVE, null, fallbackCode || 'RECORD_RESPONSE_INVALID'))
  }
  if (!response.ok) {
    const message = response.status >= 500 && data.error !== 'record_save_failed'
      ? UNCONFIRMED_SAVE
      : data.message || data.error || 'The plate could not be saved. Please try again.'
    throw new Error(formatApiError(message, data, fallbackCode))
  }
  if (data.status !== 'success') {
    throw new Error(formatApiError(UNCONFIRMED_SAVE, data, 'RECORD_RESPONSE_UNCONFIRMED'))
  }
  return data
}

export function recordSuccessMessage(category, data) {
  if (data.is_count_only) return `${data.display_name || 'Count-only plate'} recorded`
  const name = [data.preferred_name ?? data.first_name, data.last_name].filter(Boolean).join(' ').trim()
  const label = category === 'faculty' ? 'FACULTY CLEAN' : category === 'red' ? 'VERY DIRTY' : category.toUpperCase()
  const manual = category !== 'faculty' && data.is_manual_entry
    ? ' Saved as a manual entry without a unique roster match.' : ''
  return `${name || (category === 'faculty' ? 'Faculty' : 'Student')} recorded as ${label}.${manual}`
}
