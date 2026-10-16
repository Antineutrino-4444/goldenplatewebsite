import { useCallback, useEffect, useMemo, useState } from 'react'
import { ArrowLeft, ArrowUpRight, Building2, Globe2, MapPin, RefreshCcw, X } from 'lucide-react'
import AccountMenu from '@/components/AccountMenu.jsx'
import WorldMap from '@/components/WorldMap.jsx'
import SchoolLocationDialog from '@/components/SchoolLocationDialog.jsx'
import { hasGeographicCoordinates } from '@/lib/mapCoordinates.js'
import { schoolSessionLabel } from '@/lib/schoolMap.js'

function schoolPortalUrl() {
  const url = new URL('/', window.location.href)
  if (url.hostname.startsWith('map.')) url.hostname = url.hostname.slice(4)
  return url.href
}

export default function SchoolMapPortal({ app }) {
  const [schools, setSchools] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [section, setSection] = useState('mapped')
  const [filter, setFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const mapped = useMemo(() => schools.filter(hasGeographicCoordinates), [schools])
  const others = useMemo(() => schools.filter((school) => !hasGeographicCoordinates(school)), [schools])
  const selected = schools.find((school) => school.id === selectedId)
  const visibleSchools = (section === 'others' ? others : mapped).filter((school) =>
    `${school.code || ''} ${school.name}`.toLowerCase().includes(filter.trim().toLowerCase()))

  const loadSchools = useCallback(async () => {
    setError('')
    setLoading(true)
    try {
      const response = await fetch('/api/map/schools')
      const data = await response.json()
      if (!response.ok) throw new Error(data.error || 'Unable to load schools.')
      setSchools(Array.isArray(data.schools) ? data.schools : [])
    } catch {
      setError('Unable to load schools. Check your connection and try again.')
    } finally { setLoading(false) }
  }, [])

  useEffect(() => {
    const previous = document.title
    document.title = 'Explore schools · Golden Plate'
    // Old submission links now lead to the public school map.
    if (/\/(submission|submit)\/?$/.test(window.location.pathname)) {
      window.history.replaceState(null, '', window.location.hostname.startsWith('map.') ? '/' : '/map')
    }
    loadSchools()
    return () => { document.title = previous }
  }, [loadSchools])

  const selectSchool = (id) => {
    setSelectedId(id)
    const school = schools.find((candidate) => candidate.id === id)
    if (school) { setSection(hasGeographicCoordinates(school) ? 'mapped' : 'others'); setFilter('') }
  }

  return (
    <div className="min-h-screen bg-[#f5f7f5] text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-[1600px] flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-7">
          <a href={window.location.hostname.startsWith('map.') ? '/' : '/map'} className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-teal-800 text-white"><Globe2 size={23} /></span>
            <span><span className="block text-lg font-bold tracking-tight">Golden Plate</span><span className="block text-xs text-slate-500">A world of schools making a difference</span></span>
          </a>
          <nav aria-label="School map navigation" className="flex items-center gap-3">
            <a href={schoolPortalUrl()} className="flex items-center gap-1 text-sm font-medium text-slate-600 hover:text-teal-800">School portal<ArrowUpRight size={15} /></a>
            {app.user ? <AccountMenu app={app} onSchoolLocationSaved={loadSchools} /> : <a href="/login" className="rounded-lg bg-teal-800 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-900">Sign in</a>}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-[1600px] px-4 py-6 sm:px-7">
        <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
          <div><p className="mb-1 text-xs font-semibold uppercase tracking-[0.16em] text-teal-700">The Golden Plate community</p><h1 className="text-3xl font-bold tracking-tight sm:text-4xl">Explore our schools.</h1><p className="mt-2 text-sm text-slate-500">Search a school code like SAC, explore the globe, or find a school in Others.</p></div>
          <div className="rounded-full border border-slate-200 bg-white px-4 py-2 text-xs text-slate-500"><span className="font-semibold text-teal-800">{schools.length}</span> participating {schools.length === 1 ? 'school' : 'schools'} · Public map</div>
        </div>
        {error && <div role="alert" className="mb-4 flex items-center gap-3 rounded-xl border border-red-100 bg-red-50 p-3 text-sm text-red-800">{error}<button type="button" className="underline" onClick={loadSchools}>Try again</button></div>}
        <div className="grid items-start gap-5 lg:grid-cols-[290px_minmax(0,1fr)]">
          <aside className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <div className="flex items-center justify-between border-b border-slate-100 px-4 py-4"><h2 className="text-sm font-semibold">Participating schools</h2><button type="button" aria-label="Refresh schools" disabled={loading} onClick={loadSchools} className="rounded-md p-1.5 text-slate-400 hover:bg-slate-50 hover:text-teal-700"><RefreshCcw size={15} /></button></div>
            <div className="p-3">
              <div role="group" aria-label="School location group" className="mb-3 flex rounded-lg bg-slate-100 p-1 text-xs font-semibold">
                <button type="button" aria-pressed={section === 'mapped'} onClick={() => { setSection('mapped'); setFilter('') }} className={`flex-1 rounded-md px-2 py-2 ${section === 'mapped' ? 'bg-white text-teal-800 shadow-sm' : 'text-slate-500'}`}>On the map ({mapped.length})</button>
                <button type="button" aria-pressed={section === 'others'} onClick={() => { setSection('others'); setFilter('') }} className={`flex-1 rounded-md px-2 py-2 ${section === 'others' ? 'bg-white text-teal-800 shadow-sm' : 'text-slate-500'}`}>Others ({others.length})</button>
              </div>
              <label className="sr-only" htmlFor="school-list-filter">Filter participating schools by code or name</label>
              <input id="school-list-filter" value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="Filter by code or school name" className="mb-3 w-full rounded-lg border border-slate-200 px-3 py-2 text-xs outline-teal-700" />
              {loading && <p role="status" className="px-2 py-4 text-xs text-slate-500">Loading schools…</p>}
              {!loading && !visibleSchools.length && <p className="px-2 py-4 text-xs leading-5 text-slate-500">{filter ? 'No schools match this code or name.' : section === 'mapped' ? 'Schools that choose a location will appear here. Find schools without a pin in Others.' : 'All participating schools currently have a map location.'}</p>}
              <ul className="max-h-[420px] space-y-2 overflow-y-auto" aria-label={section === 'others' ? 'Schools in Others' : 'Mapped schools'}>
                {visibleSchools.map((school) => <li key={school.id}><button type="button" onClick={() => selectSchool(school.id)} className={`flex w-full gap-3 rounded-lg border p-3 text-left transition hover:border-teal-300 hover:bg-teal-50 ${selectedId === school.id ? 'border-teal-500 bg-teal-50' : 'border-slate-100'}`}>
                  <Building2 size={18} className="mt-0.5 shrink-0 text-teal-700" /><span className="min-w-0"><span className="mb-1 block text-[10px] font-bold uppercase tracking-wider text-teal-700">{school.code}</span><span className="block text-sm font-semibold">{school.name}</span><span className="mt-1 block text-xs text-slate-500">{school.address || (section === 'others' ? 'No map location' : school.location_name)}</span><span className="mt-2 block text-[11px] font-medium text-teal-700">{schoolSessionLabel(school.session_count)}</span></span>
                </button></li>)}
              </ul>
              {section === 'others' && <p className="mt-3 border-t border-slate-100 px-1 pt-3 text-[11px] leading-5 text-slate-400">Schools without a selected location and schools choosing to remain unmapped are listed here.</p>}
            </div>
          </aside>
          <div className="min-w-0 space-y-4">
            <div className="flex h-[72vh] min-h-[520px] max-h-[900px] flex-col"><WorldMap pins={schools} selectedPinId={selectedId} onSelectPin={selectSchool} fillContainer /></div>
            {selected && <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm" aria-label="Selected school details">
              <div className="flex items-start justify-between gap-3"><div><p className="mb-1 text-xs font-semibold text-teal-700">{selected.code}</p><h2 className="text-xl font-bold">{selected.name}</h2></div><button type="button" aria-label="Close school details" onClick={() => setSelectedId(null)} className="rounded-lg p-2 text-slate-400 hover:bg-slate-50"><X size={18} /></button></div>
              <p className="mt-3 flex items-start gap-2 text-sm text-slate-500"><MapPin size={16} className="mt-0.5 shrink-0" />{hasGeographicCoordinates(selected) ? selected.address || selected.location_name : 'Listed in Others without a location pin.'}</p>
              <p className="mt-3 text-sm font-semibold text-teal-700">{schoolSessionLabel(selected.session_count)}</p>
              {app.user?.role === 'inter_school' && <div className="mt-3"><SchoolLocationDialog key={selected.school_id} app={app} initialSchoolId={selected.school_id} onSaved={loadSchools} /></div>}
              {!hasGeographicCoordinates(selected) && <button type="button" onClick={() => setSection('others')} className="mt-3 flex items-center gap-1 text-xs font-medium text-teal-700"><ArrowLeft size={13} />View Others</button>}
            </section>}
          </div>
        </div>
      </main>
    </div>
  )
}
