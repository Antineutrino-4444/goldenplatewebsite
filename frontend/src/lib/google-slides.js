const driveScope = 'https://www.googleapis.com/auth/drive.file'
const slidesMime = 'application/vnd.google-apps.presentation'
const powerpointMime = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
const uploadUrl = 'https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,mimeType&ignoreDefaultVisibility=true'
const connectionError = 'Google sign-in couldn’t load. Check your connection and try again.'
let loading = null

export function loadGoogleSlidesAuth() {
  if (window.google?.accounts?.oauth2?.initTokenClient) return Promise.resolve()
  if (loading) return loading

  loading = new Promise((resolve, reject) => {
    const script = document.createElement('script')
    function finish() {
      clearTimeout(timer)
      script.onerror = script.onload = null
      if (window.google?.accounts?.oauth2?.initTokenClient) {
        resolve()
      } else {
        script.remove()
        reject(new Error(connectionError))
      }
    }
    const timer = setTimeout(finish, 15000)
    script.async = true
    script.src = 'https://accounts.google.com/gsi/client'
    script.onload = script.onerror = finish
    document.head.appendChild(script)
  }).finally(() => { loading = null })
  return loading
}

// Call directly from a button click, while the browser still allows a Google popup.
export function authorizeGoogleSlides(clientId) {
  return new Promise((resolve, reject) => {
    const oauth = window.google?.accounts?.oauth2
    if (!clientId || !oauth?.initTokenClient) {
      reject(new Error(connectionError))
      return
    }
    const client = oauth.initTokenClient({
      client_id: clientId,
      scope: driveScope,
      include_granted_scopes: false,
      prompt: 'select_account',
      callback(response) {
        if (response?.error === 'access_denied') {
          reject(new Error('Google Drive permission was declined.'))
        } else if (response?.error || !response?.access_token || !response.scope?.split(/\s+/).includes(driveScope)) {
          reject(new Error('Google couldn’t authorize creating this presentation in your Drive.'))
        } else {
          resolve(response.access_token)
        }
      },
      error_callback(error) {
        if (error?.type === 'popup_closed') {
          reject(new DOMException('Google sign-in was canceled.', 'AbortError'))
        } else if (error?.type === 'popup_failed_to_open') {
          reject(new Error('Allow the Google sign-in popup and try again.'))
        } else {
          reject(new Error('Google sign-in could not be completed.'))
        }
      },
    })
    client.requestAccessToken()
  })
}

export async function createGoogleSlidesFile({ file, filename, accessToken, signal }) {
  const name = (filename || '').replace(/[\\/\p{Cc}]/gu, ' ').trim().replace(/\.pptx$/i, '').trim() || 'School assembly'
  const boundary = 'gp-' + crypto.randomUUID()
  const body = new Blob([
    '--' + boundary + '\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n',
    JSON.stringify({ name, mimeType: slidesMime }),
    '\r\n--' + boundary + '\r\nContent-Type: ' + powerpointMime + '\r\n\r\n',
    file,
    '\r\n--' + boundary + '--\r\n',
  ])
  const uncertainResult = 'Check Google Drive for your presentation before trying again.'
  let response
  try {
    response = await fetch(uploadUrl, {
      method: 'POST',
      credentials: 'omit',
      redirect: 'error',
      headers: { Authorization: 'Bearer ' + accessToken, 'Content-Type': 'multipart/related; boundary=' + boundary },
      body,
      signal,
    })
  } catch (error) {
    if (signal?.aborted || error?.name === 'AbortError') throw error
    throw new Error('The Google Drive connection was interrupted. ' + uncertainResult)
  }
  if (response.status === 401) throw new Error('Google sign-in expired. Sign in again to create the presentation.')
  if (response.status === 403) throw new Error('Google Drive didn’t allow this presentation to be created in the selected account.')
  if (!response.ok) throw new Error('Google Drive could not confirm creation. ' + uncertainResult)
  const result = await response.json().catch(() => null)
  if (result?.mimeType !== slidesMime || typeof result.id !== 'string' || !/^[A-Za-z0-9_-]+$/.test(result.id)) {
    throw new Error('Google Drive didn’t return a Google Slides link. ' + uncertainResult)
  }
  return 'https://docs.google.com/presentation/d/' + result.id + '/edit'
}
