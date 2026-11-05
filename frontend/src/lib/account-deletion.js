import { readApiJson } from './api-errors.js'
export async function beginOwnAccountDeletion(app) {
  try {
    const response = await fetch('/api/account-deletion/self', { method: 'POST' })
    const data = await readApiJson(response)
    if (!response.ok) throw new Error(data.error || 'Unable to start account deletion.')
    window.location.assign(`/account-deletion#token=${encodeURIComponent(data.token)}`)
  } catch (failure) {
    app.showMessage(failure.message || 'Unable to connect. Please try again.', 'error')
  }
}
