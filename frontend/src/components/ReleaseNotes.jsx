import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'

function ReleaseBody({ markdown }) {
  return markdown.split(/\n\s*\n/).map((block, index) => {
    const lines = block.split('\n')
    if (lines.every((line) => /^[-*] /.test(line))) {
      return <ul key={index} className="list-disc space-y-1 pl-5">
        {lines.map((line, item) => <li key={item}>{line.slice(2)}</li>)}
      </ul>
    }
    return <p key={index}>{lines.join(' ')}</p>
  })
}

function ReleaseEntry({ version, markdown }) {
  const byline = /(?:^|\n[ \t]*\n)Authors?:[ \t]+([^\n]+)(?=\n[ \t]*\n|$)/
  const author = markdown.match(byline)?.[1].trim()
  return <section className="space-y-2 border-t pt-3">
    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
      <h3 className="font-semibold">Version {version}</h3>
      {author && <p className="text-muted-foreground">
        {author === 'Pending Git attribution'
          ? 'Author credit pending'
          : <>By <span className="font-semibold text-[var(--site-gold-ink)]">{author}</span></>}
      </p>}
    </div>
    <ReleaseBody markdown={markdown.replace(byline, '').trim()} />
  </section>
}

export default function ReleaseNotes({ history = false, onClose, onCloseAutoFocus }) {
  const [entries, setEntries] = useState(null)
  const [loadFailed, setLoadFailed] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    fetch(history ? '/api/release-notes?view=history' : '/api/release-notes', { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error('Release notes failed to load')
        return response.json()
      })
      .then((data) => { if (!controller.signal.aborted) setEntries(data.entries) })
      .catch(() => { if (!controller.signal.aborted) setLoadFailed(true) })
    return () => controller.abort()
  }, [history])

  async function acknowledge() {
    setSaving(true)
    setError(false)
    try {
      const response = await fetch('/api/release-notes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ version: entries[0].version }),
      })
      if (!response.ok) throw new Error('Acknowledgment failed')
      setEntries([])
    } catch {
      setError(true)
    } finally {
      setSaving(false)
    }
  }

  if (!history && !entries?.length) return null

  function close() {
    if (history) onClose()
    else setEntries([])
  }

  return <Dialog open onOpenChange={(open) => { if (!open && !saving) close() }}>
    <DialogContent aria-describedby={undefined} dismissOnOverlayClick={false} onCloseAutoFocus={onCloseAutoFocus} className={history ? "sm:max-w-2xl" : "sm:max-w-xl"}>
      <DialogHeader>
        <DialogTitle>{history ? "Release history" : "What’s new in Golden Plate"}</DialogTitle>
      </DialogHeader>
      {history && !entries && (loadFailed
        ? <p role="alert" className="text-sm text-destructive">Couldn’t load release history. Close and reopen it to try again.</p>
        : <p role="status" className="text-sm">Loading release history…</p>)}
      {history && entries?.length === 0 && <p className="text-sm">No release notes have been published yet.</p>}
      {!!entries?.length && <div className="max-h-[50dvh] space-y-4 overflow-y-auto text-sm leading-relaxed" tabIndex={0} role="region" aria-label="Release notes">
        {entries.map(({ version, markdown }) => <ReleaseEntry key={version} version={version} markdown={markdown} />)}
      </div>}
      {error && <p role="alert" className="text-sm text-destructive">Couldn’t save your acknowledgment. Try again, or close to read the notes later.</p>}
      <DialogFooter>
        {history ? <Button onClick={close}>Done</Button> : <Button onClick={acknowledge} disabled={saving}>{saving ? 'Saving…' : 'Got it'}</Button>}
      </DialogFooter>
    </DialogContent>
  </Dialog>
}
