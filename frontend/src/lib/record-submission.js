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
    data = await response.json()
  } catch {
    throw new Error('Could not confirm whether the plate was saved. Check Plate Tracking History before trying again.')
  }
  if (!data || typeof data !== 'object') {
    throw new Error('Could not confirm whether the plate was saved. Check Plate Tracking History before trying again.')
  }
  if (!response.ok) {
    throw new Error(data.message || data.error || 'The plate could not be saved. Please try again.')
  }
  if (data.status !== 'success') {
    throw new Error('Could not confirm whether the plate was saved. Check Plate Tracking History before trying again.')
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
