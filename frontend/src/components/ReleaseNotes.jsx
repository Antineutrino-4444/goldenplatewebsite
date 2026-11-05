import { readApiJson } from '../lib/api-errors.js'
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

export function ReleaseEntry({ version, markdown, publicHistory = false }) {
  const byline = /(?:^|\n[ \t]*\n)Authors?:[ \t]+([^\n]+)(?=\n[ \t]*\n|$)/
  const author = markdown.match(byline)?.[1].trim()
  const id = `version-${version}`
  const Heading = publicHistory ? 'h2' : 'h3'
  return <section id={publicHistory ? id : undefined} className={publicHistory
    ? 'space-y-3 border-t py-6'
    : 'space-y-2 border-t pt-3'}>
    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
      <Heading className={publicHistory ? undefined : 'font-semibold'}>
        {publicHistory ? <a href={`#${id}`}>Version {version}</a> : `Version ${version}`}
      </Heading>
      {author && <p className="text-muted-foreground">
        {author === 'Pending Git attribution'
          ? 'Author credit pending'
          : <>By <span className="font-semibold text-[var(--site-gold-ink)]">{author}</span></>}
      </p>}
    </div>
    <div className={publicHistory ? 'grid gap-3' : 'space-y-2'}>
      <ReleaseBody markdown={markdown.replace(byline, '').trim()} />
    </div>
  </section>
}

export default function ReleaseNotes() {
  const [entries, setEntries] = useState(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    fetch('/api/release-notes', { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error('Release notes failed to load')
        return readApiJson(response)
      })
      .then((data) => { if (!controller.signal.aborted) setEntries(data.entries) })
      .catch(() => { if (!controller.signal.aborted) setEntries([]) })
    return () => controller.abort()
  }, [])

  async function acknowledge() {
    setSaving(true)
    setError('')
    try {
      const response = await fetch('/api/release-notes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ version: entries[0].version }),
      })
      if (!response.ok) throw new Error((await readApiJson(response)).error)
      setEntries([])
    } catch (failure) {
      setError(failure.message || 'Couldn’t save your acknowledgment. Try again, or close to read the notes later.')
    } finally {
      setSaving(false)
    }
  }

  if (!entries?.length) return null

  return <Dialog open onOpenChange={(open) => { if (!open && !saving) setEntries([]) }}>
    <DialogContent aria-describedby={undefined} dismissOnOverlayClick={false} className="sm:max-w-xl">
      <DialogHeader>
        <DialogTitle>What’s new in Golden Plate</DialogTitle>
      </DialogHeader>
      <div className="max-h-[50dvh] space-y-4 overflow-y-auto text-sm leading-relaxed" tabIndex={0} role="region" aria-label="Release notes">
        {entries.map(({ version, markdown }) => <ReleaseEntry key={version} version={version} markdown={markdown} />)}
      </div>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      <DialogFooter>
        <Button onClick={acknowledge} disabled={saving}>{saving ? 'Saving…' : 'Got it'}</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
}
