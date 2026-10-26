import VideoHelp from '@/components/VideoHelp.jsx'
import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { MapPinned } from 'lucide-react'
import { Button } from '@/components/ui/button.jsx'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog.jsx'
import { formatCoordinates, hasGeographicCoordinates } from '@/lib/mapCoordinates.js'
import PlaceSearch from '@/components/PlaceSearch.jsx'

const WorldMap = lazy(() => import('@/components/WorldMap.jsx'))

function SchoolLocationEditor({ app, onSaved, onClose, schoolId, hideHeader = false, onSavingChange }) {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [canEdit, setCanEdit] = useState(false)
  const [schoolName, setSchoolName] = useState(app.user?.school?.name || 'Your school')
  const [point, setPoint] = useState(null)
  const [focusPoint, setFocusPoint] = useState(null)
  const [loaded, setLoaded] = useState(false)
  const [unmapped, setUnmapped] = useState(false)
  const [loadAttempt, setLoadAttempt] = useState(0)
  const locationUrl = `/api/map/school-location${schoolId ? `?school_id=${encodeURIComponent(schoolId)}` : ''}`

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError('')
    fetch(locationUrl, { signal: controller.signal }).then(async (response) => {
      const data = await response.json()
      if (controller.signal.aborted) return
      if (!response.ok) throw new Error(data.error || 'Unable to load your school location.')
      setSchoolName(data.school_name)
      setCanEdit(data.can_edit)
      setUnmapped(data.location_state === 'unmapped')
      setPoint(data.location)
      setFocusPoint(data.location)
      setLoaded(true)
    }).catch((failure) => {
      if (failure.name !== 'AbortError') setError(failure.message)
    }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [loadAttempt, locationUrl])

  const save = async (remainUnmapped = false) => {
    if (saving || !canEdit || (!remainUnmapped && !hasGeographicCoordinates(point))) return
    setSaving(true)
    onSavingChange?.(true)
    setError('')
    try {
      const response = await fetch(locationUrl, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(remainUnmapped ? { unmapped: true } : { ...point, unmapped: false, location_name: point.location_name || point.name || schoolName }),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.error || 'Unable to save your school location.')
      app.showMessage?.(remainUnmapped ? `${schoolName} will remain unmapped and appear under Others` : `Location saved for ${schoolName}`, 'success')
      onSaved?.(data.location)
      onClose()
    } catch (failure) {
      setError(failure.message || 'Unable to save your school location. Please try again.')
    } finally {
      setSaving(false)
      onSavingChange?.(false)
    }
  }

  return (
    <>
      {!hideHeader && <DialogHeader>
        <DialogTitle>Choose your school’s location</DialogTitle>
        <DialogDescription>Put {schoolName} on the community map, or join the school list without a pin.</DialogDescription>
      </DialogHeader>}
      <VideoHelp videos={[26]} label="Watch: place your school on the map" />
      {error && <div className="space-y-2"><p role="alert" className="text-sm text-red-700">{error}</p>{!loaded && !loading && <Button variant="outline" onClick={() => setLoadAttempt((attempt) => attempt + 1)}>Try again</Button>}</div>}
      {unmapped && <p role="status" className="rounded-md border bg-slate-50 p-3 text-sm text-slate-600">Listed in Others without a map pin. You can add a location here.</p>}
      {loading ? <p role="status" className="p-6 text-sm text-slate-600">Loading school location…</p> : loaded && (
        <div className="grid min-w-0 gap-4 md:grid-cols-[minmax(0,0.8fr)_minmax(0,1.4fr)]">
          <div className="min-w-0 space-y-3">
            <div className="overflow-hidden rounded-md border">
              <PlaceSearch placesOnly initialQuery={schoolName} onChoose={(place) => {
                setUnmapped(false)
                setPoint({ ...place, location_name: place.name })
                setFocusPoint(place)
              }} />
            </div>
            <div className="rounded-md border bg-slate-50 p-3 text-sm">
              <p className="font-semibold text-slate-900">{point?.location_name || 'Choose a school or place a pin'}</p>
              {point?.address && <p className="mt-1 text-slate-600">{point.address}</p>}
              <p className="mt-1 text-xs text-slate-500">{formatCoordinates(point)}</p>
            </div>
            {!canEdit && <p className="text-sm text-slate-600">You can search and preview a location. Ask a school superadmin or interschool admin to save it.</p>}
          </div>
          <Suspense fallback={<p role="status" className="p-6 text-sm text-slate-600">Loading map…</p>}>
            <WorldMap
              showSearch={false}
              compact
              pendingPoint={point}
              focusPoint={focusPoint}
              onMapClick={(latitude, longitude) => {
                setUnmapped(false)
                setPoint((previous) => ({
                  latitude, longitude, location_name: previous?.location_name || schoolName,
                  address: previous?.address || '', source: 'manual', place_id: '',
                }))
              }}
            />
          </Suspense>
        </div>
      )}
      <div className="flex flex-wrap justify-end gap-2">
        <Button variant="outline" onClick={onClose} disabled={saving}>Not now</Button>
        {canEdit && <>
          <Button variant="outline" onClick={() => save(true)} disabled={saving || loading}>Remain unmapped</Button>
          <Button onClick={() => save(false)} disabled={saving || !hasGeographicCoordinates(point)} className="bg-teal-700 hover:bg-teal-800">{saving ? 'Saving…' : 'Save school location'}</Button>
        </>}
      </div>
    </>
  )
}

function InterschoolLocationEditor({ app, onSaved, onClose, initialSchoolId = '' }) {
  const [schools, setSchools] = useState([])
  const [schoolId, setSchoolId] = useState(initialSchoolId)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError('')
    fetch('/api/map/schools', { signal: controller.signal }).then(async (response) => {
      const data = await response.json()
      if (!response.ok) throw new Error(data.error || 'Unable to load schools.')
      if (!controller.signal.aborted) setSchools(data.schools || [])
    }).catch((failure) => {
      if (failure.name !== 'AbortError') setError(failure.message || 'Unable to load schools.')
    }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [attempt])

  const selected = schools.find((school) => school.school_id === schoolId)
  return (
    <>
      <DialogHeader>
        <DialogTitle>Manage school locations</DialogTitle>
        <DialogDescription>Choose a school, then search for its location or place a pin. You can also keep it unmapped in Others.</DialogDescription>
      </DialogHeader>
      {loading ? <p role="status" className="text-sm text-slate-600">Loading schools…</p> : error ? (
        <div className="space-y-2"><p role="alert" className="text-sm text-red-700">{error}</p><Button variant="outline" onClick={() => setAttempt((value) => value + 1)}>Try again</Button></div>
      ) : (
        <div className="space-y-2">
          <label htmlFor="school-location-target" className="block text-sm font-semibold">School to manage</label>
          <select id="school-location-target" value={selected ? schoolId : ''} disabled={busy}
            onChange={(event) => setSchoolId(event.target.value)} className="w-full rounded-md border bg-white px-3 py-2 text-sm">
            <option value="">Choose a school…</option>
            {schools.map((school) => <option key={school.school_id} value={school.school_id}>{school.code} · {school.name}</option>)}
          </select>
          {!schools.length && <p className="text-sm text-slate-600">No active schools are available.</p>}
        </div>
      )}
      {!loading && !error && selected ? (
        <SchoolLocationEditor key={schoolId} app={app} schoolId={schoolId} hideHeader
          onSaved={onSaved} onClose={onClose} onSavingChange={setBusy} />
      ) : <div className="flex justify-end"><Button variant="outline" onClick={onClose}>Close</Button></div>}
    </>
  )
}

export default function SchoolLocationDialog({
  app, onSaved, open: controlledOpen, onOpenChange, hideTrigger = false,
  autoPrompt = false, allowAutomaticPrompt = true, onCloseAutoFocus, initialSchoolId = '',
}) {
  const [internalOpen, setInternalOpen] = useState(false)
  const open = controlledOpen ?? internalOpen
  const setOpen = onOpenChange || setInternalOpen
  const promptChecked = useRef(false)

  useEffect(() => {
    if (!autoPrompt || app.user?.role !== 'superadmin' || !allowAutomaticPrompt || promptChecked.current) return
    if (open) {
      promptChecked.current = true
      return
    }
    const controller = new AbortController()
    fetch('/api/map/school-location', { signal: controller.signal }).then(async (response) => {
      if (!response.ok) throw new Error('Unable to check school location')
      const data = await response.json()
      promptChecked.current = true
      if (data.decision_required) setOpen(true)
    }).catch(() => {
      // An unavailable preference check must not override an unmapped choice.
      // The account menu remains available, and the next visit retries the check.
    })
    return () => controller.abort()
  }, [autoPrompt, allowAutomaticPrompt, open, app.user?.id, app.user?.role, setOpen])

  if (!app.user || !['user', 'admin', 'superadmin', 'inter_school'].includes(app.user.role)) return null
  return (
    <>
      {!hideTrigger && <Button variant="outline" size="sm" onClick={() => setOpen(true)}><MapPinned className="mr-2 h-4 w-4" />{app.user.role === 'inter_school' ? 'School locations' : 'School location'}</Button>}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-4xl max-h-[90vh] overflow-y-auto" dismissOnOverlayClick={false} onCloseAutoFocus={onCloseAutoFocus}>
          {open && (app.user.role === 'inter_school'
            ? <InterschoolLocationEditor app={app} initialSchoolId={initialSchoolId} onSaved={onSaved} onClose={() => setOpen(false)} />
            : <SchoolLocationEditor app={app} onSaved={onSaved} onClose={() => setOpen(false)} />)}
        </DialogContent>
      </Dialog>
    </>
  )
}
