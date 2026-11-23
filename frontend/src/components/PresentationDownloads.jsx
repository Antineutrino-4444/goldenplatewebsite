import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog.jsx'
import { assemblyAction, formats, liveProviders, liveReturnNotice, needsGoogleSlidesNotice, presentationFileName, presentationLoginPath, readPresentationOptions, schoolLabelOption } from '@/lib/presentation-options.js'
import { useLiveAssembly } from '@/lib/use-live-assembly.js'
import { authorizeGoogleSlides, createGoogleSlidesFile, loadGoogleSlidesAuth } from '@/lib/google-slides.js'

const googleSlidesUrl = 'https://slides.google.com/create'
const googleClientId = import.meta.env.VITE_GOOGLE_SLIDES_CLIENT_ID?.trim()

const googleDialogCopy = {
  manual: {
    title: 'Import into Google Slides',
    description: 'Download the PowerPoint file, then import it into a new or existing Google Slides presentation. Download and import again for newer results.',
    button: 'Download for Google Slides',
  },
  google: {
    title: 'Create a Google Slides copy',
    description: 'This saves the current school results in your Google Drive. Create another copy when you want newer results.',
    button: 'Create in Google Slides',
  },
  live: {
    title: 'Connect a live Google Slides deck',
    description: 'Golden Plate updates the same Google Drive file after lunch results change. Updates replace its contents. Make a separate copy for edits you want to keep.',
    button: 'Continue to Google Slides',
  },
}

function GoogleSlidesDialog({ selection, onClose, onConfirm, trigger }) {
  if (!selection) return null
  const copy = googleDialogCopy[selection.action]
  return <Dialog open onOpenChange={open => { if (!open) onClose() }}>
    <DialogContent className="gp-import-dialog" onCloseAutoFocus={(event) => {
      event.preventDefault()
      trigger.current?.focus()
    }}>
      <DialogHeader>
        <DialogTitle>{copy.title}</DialogTitle>
        <DialogDescription>{copy.description}</DialogDescription>
      </DialogHeader>
      {selection.action === 'manual' && <ol>
        <li>In Google Slides, choose <strong>File → Import slides → Upload</strong> and select the downloaded file.</li>
        <li>Choose the slides you want, keep <strong>Keep original theme</strong> selected, then choose <strong>Import slides</strong>.</li>
      </ol>}
      <p>Google Slides may substitute fonts and change line breaks. Results appear without PowerPoint’s transitions or animated reveals.</p>
      <div className="gp-import-actions">
        <button type="button" className="gp-button" onClick={onConfirm}>{copy.button}</button>
        <button type="button" className="gp-text-link" onClick={onClose}>Cancel</button>
      </div>
    </DialogContent>
  </Dialog>
}

function saveFile(url, filename) {
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.append(link)
  link.click()
  link.remove()
}

export default function PresentationDownloads({ theme }) {
  const { search } = useLocation()
  return <PresentationForm key={search} search={search} theme={theme} />
}

function PresentationForm({ search, theme }) {
  const navigate = useNavigate()
  const [options, setOptions] = useState(() => readPresentationOptions(search))
  const [notice, setNotice] = useState(() => liveReturnNotice(search))
  const [busy, setBusy] = useState(false)
  const [googleSelection, setGoogleSelection] = useState(null)
  const [googleAuth, setGoogleAuth] = useState('loading')
  const [authAttempt, setAuthAttempt] = useState(0)
  const pending = useRef(null)
  const trigger = useRef(null)
  const schoolField = useRef(null)
  const labelField = useRef(null)
  const { kind, format, schoolCode, schoolLabel, linkedTheme } = options
  // A bookmarked cloud deck or an OAuth return can identify an existing themed file.
  const liveTheme = linkedTheme || theme
  const loginPath = presentationLoginPath({ format, schoolCode, schoolLabel, theme: liveTheme })
  const provider = liveProviders[format]
  const live = useLiveAssembly(schoolCode, liveTheme, provider)
  const savedLabel = live.link?.school_label || ''
  const displayLabel = schoolLabel ?? savedLabel
  const labelChanged = schoolLabel != null && schoolLabelOption(schoolLabel).school_label !== savedLabel
  const directSlides = format === 'google-slides' && !live.loading && !live.enabled && Boolean(googleClientId)
  const primary = assemblyAction(format, live, directSlides, labelChanged)
  useEffect(() => () => pending.current?.abort(), [])
  useEffect(() => {
    if (!directSlides) return
    let active = true
    loadGoogleSlidesAuth().then(
      () => { if (active) setGoogleAuth('ready') },
      () => { if (active) setGoogleAuth('unavailable') },
    )
    return () => { active = false }
  }, [directSlides, authAttempt])

  function choose(key, value) {
    setOptions((previous) => ({
      ...previous, [key]: value,
      ...(key === 'schoolCode' && value.trim() !== previous.schoolCode.trim() ? { schoolLabel: null } : {}),
      ...(key === 'schoolLabel' ? {} : { linkedTheme: null }),
    }))
    setNotice(null)
  }

  async function runAction(action) {
    if (pending.current) return
    const request = new AbortController()
    pending.current = request
    setBusy(true)
    setNotice(null)
    try {
      await action(request.signal)
    } catch (error) {
      if (!request.signal.aborted) {
        if (error?.name === 'AbortError') setNotice({ type: 'cancelled', message: 'Google Slides creation canceled.' })
        else setNotice({ type: 'error', message: error.message || 'Couldn’t prepare the presentation.' })
      }
    } finally {
      pending.current = null
      if (!request.signal.aborted) setBusy(false)
    }
  }

  async function reportProblem(response) {
    const problem = await response.json().catch(() => ({}))
    if (response.status === 401) {
      setNotice({ type: 'login', message: 'Sign in with an account at this school to continue.' })
    } else if (problem.code === 'ACCOUNT_EMAIL_REQUIRED') {
      setNotice({ type: 'verify', message: 'Your school requires a verified account email to continue.' })
    } else if (problem.code === 'WRONG_SCHOOL_ACCOUNT') {
      setNotice({ type: 'switch', message: 'Use an account belonging to this school to continue.' })
    } else {
      if (response.status === 404) schoolField.current?.focus()
      setNotice({ type: 'error', message: problem.error || 'Couldn’t prepare this presentation. Please try again.' })
    }
  }

  function exportPresentation(createInDrive = false) {
    return runAction(async signal => {
      const extension = format === 'pdf' ? 'pdf' : 'pptx'
      // Start Google's account chooser in the click gesture. The website still
      // checks school access before any deck can be sent to Drive.
      const accessToken = createInDrive ? await authorizeGoogleSlides(googleClientId) : null
      if (signal.aborted) return
      const response = await fetch('/api/resources/presentations/download', {
        method: 'POST', credentials: 'same-origin', signal,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kind, theme, format, school_code: schoolCode.trim(),
          ...schoolLabelOption(schoolLabel ?? live.link?.school_label) }),
      })
      if (!response.ok) return reportProblem(response)
      const file = await response.blob()
      const filename = presentationFileName(response.headers.get('Content-Disposition'), 'school-assembly.' + extension)
      if (createInDrive) {
        const url = await createGoogleSlidesFile({ file, filename, accessToken, signal })
        if (signal.aborted) return
        setNotice({ type: 'created', message: 'Your presentation is ready.', url })
        window.location.assign(url)
        return
      }
      const url = URL.createObjectURL(file)
      try {
        saveFile(url, filename)
      } finally {
        window.setTimeout(() => URL.revokeObjectURL(url), 60000)
      }
      setNotice({ type: 'done', message: 'Download started.' })
    })
  }

  function changeLiveDeck({ disconnect = false, googleConfirmed = false } = {}) {
    return runAction(async signal => {
      const path = '/api/resources/presentations/live' + (disconnect ? '' : '/connect')
      const response = await fetch(path, {
        method: disconnect ? 'DELETE' : 'POST', credentials: 'same-origin', signal,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ school_code: schoolCode.trim(), theme: liveTheme, provider,
          ...schoolLabelOption(disconnect ? null : schoolLabel) }),
      })
      if (!response.ok) return reportProblem(response)
      if (disconnect) {
        live.refresh()
        setNotice({ type: 'stopped', message: 'Automatic updates stopped for this deck.' })
        return
      }
      const connection = await response.json()
      if (signal.aborted) return
      if (response.status === 202) {
        live.refresh()
        const message = connection.status === 'retry' ? 'The latest results could not be synced yet.' : 'Your live deck is being prepared.'
        setNotice({ type: 'queued', message, url: connection.url })
        return
      }
      const url = connection.authorization_url || connection.url
      if (url && new URL(url).protocol === 'https:') {
        // A saved connection may have expired since the page checked its status.
        if (provider === 'google' && connection.authorization_url && !googleConfirmed) {
          setGoogleSelection({ action: 'live', authorizationUrl: url })
        } else {
          window.location.assign(url)
        }
      } else {
        throw new Error('The cloud service did not return a presentation link. Please try again.')
      }
    })
  }

  function confirmGoogleSelection() {
    const { action, authorizationUrl } = googleSelection
    setGoogleSelection(null)
    if (authorizationUrl) return window.location.assign(authorizationUrl)
    if (action === 'live') return changeLiveDeck({ googleConfirmed: true })
    return exportPresentation(action === 'google')
  }

  function submit(event) {
    event.preventDefault()
    if (!schoolCode.trim()) {
      schoolField.current.focus()
      setNotice({ type: 'error', message: 'Enter your school code.' })
      return
    }
    if ([...schoolLabelOption(displayLabel).school_label].length > 200) {
      labelField.current.focus()
      setNotice({ type: 'error', message: 'Use 200 characters or fewer for the school name on slides.' })
      return
    }
    const submitter = event.nativeEvent.submitter
    const action = submitter?.value || primary.value
    if (action === 'google' && googleAuth !== 'ready') return
    trigger.current = submitter || document.activeElement
    if (needsGoogleSlidesNotice(action, format, live.link)) {
      setGoogleSelection({ action })
      return
    }
    if (action === 'live') return changeLiveDeck()
    exportPresentation()
  }

  async function copyLiveLink() {
    try {
      await navigator.clipboard.writeText(live.link.url)
      setNotice({ type: 'copied', message: 'Live deck link copied.' })
    } catch {
      setNotice({ type: 'link', url: live.link.url, message: 'Copy or bookmark your live presentation link.' })
    }
  }

  async function switchAccount() {
    if (pending.current) return
    const request = new AbortController()
    pending.current = request
    setBusy(true)
    try {
      const response = await fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin', signal: request.signal })
      if (!response.ok) throw new Error()
      navigate(loginPath)
    } catch {
      if (!request.signal.aborted) setNotice({ type: 'switch', message: 'Couldn’t switch accounts. Try again.' })
    } finally {
      pending.current = null
      if (!request.signal.aborted) setBusy(false)
    }
  }

  return <section id="assembly" className="gp-decks gp-container" aria-labelledby="assembly-title">
    <h1 id="assembly-title">School assembly slides</h1>
    <form onSubmit={submit} aria-busy={busy}>
      <div className="gp-deck-workspace">
        <div className="gp-deck-settings">
          <p>Present your school’s clean-plate total, latest lunch and change since the previous session.</p>
          <fieldset disabled={busy} className="gp-deck-fields">
            <legend className="sr-only">Presentation options</legend>
            <label>
              School code
              <input ref={schoolField} name="school_code" value={schoolCode} required maxLength={64} autoCapitalize="none" spellCheck={false} onChange={(event) => choose('schoolCode', event.target.value)} />
            </label>
            <label>Format
              <select value={format} onChange={(event) => choose('format', event.target.value)}>
                {Object.entries(formats).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
            <label className="gp-deck-label-override">
              School name on slides (optional)
              <input ref={labelField} name="school_label" value={displayLabel} placeholder={live.schoolName || ''}
                aria-describedby="gp-deck-label-hint" onChange={event => choose('schoolLabel', event.target.value)} />
            </label>
          </fieldset>
          <p className="gp-deck-field-hint" id="gp-deck-label-hint">
            {displayLabel && live.schoolName ? `Clear this field to use ${live.schoolName}.` : 'Leave blank to use your school’s registered name.'}
          </p>
          {live.enabled ? <p className="gp-deck-note">
            Golden Plate updates the same deck in your {provider === 'google' ? 'Google Drive' : 'OneDrive'} when lunch results change.
            {' '}Bookmark its link for your next assembly. Make a separate copy for edits you want to keep.
          </p> : <p className="gp-deck-note">{directSlides
            ? 'This creates a one-time copy of your school’s results in Google Drive.'
            : 'Results are current at download. Download again after your next lunch to update the figures.'}</p>}
          <div className="gp-deck-submit">
            <button type="submit" value={primary.value} disabled={busy || (provider && live.loading) || (directSlides && googleAuth !== 'ready')} className="gp-button">
              {busy ? 'Please wait…' : primary.label}
            </button>
            {live.enabled && <button type="submit" value={format === 'google-slides' ? 'manual' : 'download'} disabled={busy || live.loading} className="gp-text-link">Download a snapshot</button>}
            {directSlides && <button type="submit" value="manual" disabled={busy} className="gp-text-link">Download for manual import</button>}
          </div>
          {live.link && <div className="gp-deck-status">
            {!live.enabled && <span>Automatic updates for this cloud account are unavailable on this site.</span>}
            {live.enabled && live.link.status === 'reconnect' && <span>Reconnect your cloud account to resume updates.</span>}
            {live.link.status === 'retry' && <span>Golden Plate will retry the latest update.</span>}
            {live.link.status === 'pending' && <span>Your deck is waiting for its first update.</span>}
            {live.link.url && <button type="button" className="gp-text-link" disabled={busy} onClick={copyLiveLink}>Copy deck link</button>}
            <button type="button" className="gp-text-link" disabled={busy} onClick={() => changeLiveDeck({ disconnect: true })}>Stop automatic updates</button>
          </div>}
          {provider && live.unavailable && <div className="gp-deck-status" role="status">
            <span>Couldn’t check for live decks.</span>
            <button type="button" className="gp-text-link" onClick={live.refresh}>Try again</button>
          </div>}
          {directSlides && googleAuth === 'unavailable' && <div className="gp-deck-status" role="status">
            <span>Google sign-in couldn’t load.</span>
            <button className="gp-text-link" type="button" onClick={() => {
              setGoogleAuth('loading')
              setAuthAttempt(value => value + 1)
            }}>Try Google again</button>
          </div>}
          {notice && !(notice.type === 'queued' && live.link?.status === 'ready') && <div className="gp-deck-status" role={notice.type === 'error' ? 'alert' : 'status'}>
            <span>{notice.message}</span>
            {notice.type === 'login' && <Link className="gp-text-link" to={loginPath}>Sign in to this school</Link>}
            {notice.type === 'verify' && <Link className="gp-text-link" to={loginPath}>Verify account email</Link>}
            {notice.type === 'switch' && <button type="button" className="gp-text-link" onClick={switchAccount} disabled={busy}>Sign out and switch accounts</button>}
            {notice.type === 'done' && format === 'google-slides' && <a className="gp-text-link" href={googleSlidesUrl} target="_blank" rel="noopener noreferrer">Open Google Slides</a>}
            {notice.type === 'created' && <a className="gp-text-link" href={notice.url}>Open your presentation</a>}
            {notice.type === 'link' && <a className="gp-text-link" href={notice.url}>Live presentation</a>}
            {notice.type === 'queued' && notice.url && <a className="gp-text-link" href={notice.url}>Open last synced version</a>}
          </div>}
        </div>
        <figure className="gp-deck-photo">
          <img src="/images/initiative/student-developers.webp" alt="Student organizers showing the Golden Plate recorder on their phones at St. Andrew’s College" width="1600" height="1143" loading="lazy" />
          <figcaption>Golden Plate organizers in the St. Andrew’s dining hall.</figcaption>
        </figure>
      </div>
    </form>
    <GoogleSlidesDialog selection={googleSelection} onClose={() => setGoogleSelection(null)} onConfirm={confirmGoogleSelection} trigger={trigger} />
  </section>
}
