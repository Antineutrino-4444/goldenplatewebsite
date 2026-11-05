export function formatApiError(message, data, fallbackCode) {
  const code = data?.error_code || data?.code || fallbackCode
  const reference = data?.error_reference
  return [message, code && `[${code}]`, reference && `Ref ${reference}`].filter(Boolean).join(' ')
}

export async function readApiJson(response) {
  if (response.ok) return response.json()

  let data
  try {
    data = await response.json()
  } catch (error) {
    if (error.name === 'AbortError') throw error
  }
  const message = data?.message || data?.error || 'The request failed. Please try again.'
  const display = formatApiError(message, data, `HTTP_${response.status}`)
  return { ...data, error: display, message: display }
}
