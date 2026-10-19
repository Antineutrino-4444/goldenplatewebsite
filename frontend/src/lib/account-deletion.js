export async function beginOwnAccountDeletion(app) {
  try {
    const response = await fetch('/api/account-deletion/self', { method: 'POST' })
    const data = await response.json()
    if (!response.ok) throw new Error(data.error || 'Unable to start account deletion.')
    window.location.assign(`/account-deletion#token=${encodeURIComponent(data.token)}`)
  } catch (failure) {
    app.showMessage(failure.message || 'Unable to connect. Please try again.', 'error')
  }
}
