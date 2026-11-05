import { readApiJson } from '../lib/api-errors.js'
import { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { PublicFooter } from '@/components/LandingPage.jsx'
import { ReleaseEntry } from '@/components/ReleaseNotes.jsx'

export default function ReleaseHistoryPage() {
  const { hash } = useLocation()
  const [entries, setEntries] = useState(null)
  const [loadError, setLoadError] = useState('')
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    document.title = 'Release history · Golden Plate'
    const controller = new AbortController()
    fetch('/api/release-notes?view=history', { signal: controller.signal })
      .then(async (response) => {
        const data = await readApiJson(response)
        if (!response.ok) throw new Error(data.error)
        return data
      })
      .then((data) => { if (!controller.signal.aborted) setEntries(data.entries) })
      .catch((failure) => { if (!controller.signal.aborted) setLoadError(failure.message || 'Couldn’t load the release history.') })
    return () => controller.abort()
  }, [attempt])

  useEffect(() => {
    if (entries && /^#version-\d+(\.\d+){3}$/.test(hash)) {
      document.getElementById(hash.slice(1))?.scrollIntoView({ behavior: 'instant' })
    }
  }, [entries, hash])

  return <div className="golden-public">
    <main id="main-content" className="gp-container gp-release-history py-12 sm:py-16">
      <div className="max-w-[70ch]">
        <header className="mb-8 grid gap-3">
          <h1>Release history</h1>
          <p className="text-muted-foreground">What’s changed in Golden Plate, newest first.</p>
        </header>
        {loadError ? <div role="alert" className="gp-session-state">
          <p>{loadError}</p>
          <button className="gp-text-link" onClick={() => { setLoadError(''); setAttempt(attempt + 1) }}>Try again</button>
        </div> : entries ? (
          entries.length ? entries.map((entry) => <ReleaseEntry key={entry.version} {...entry} publicHistory />)
            : <p>No release notes have been published yet.</p>
        ) : <p role="status">Loading release history…</p>}
      </div>
    </main>
    <PublicFooter />
  </div>
}
