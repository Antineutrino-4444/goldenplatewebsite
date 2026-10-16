import { useEffect, useId, useRef, useState } from 'react'
import { MapPin, Search } from 'lucide-react'

export default function PlaceSearch({ onChoose, initialQuery = '', placesOnly = false }) {
  const inputId = useId()
  const [query, setQuery] = useState(initialQuery)
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState(null)
  const requestRef = useRef(null)
  const sequence = useRef(0)

  useEffect(() => () => { sequence.current += 1; requestRef.current?.abort() }, [])

  const search = async (event) => {
    event.preventDefault()
    event.stopPropagation()
    const term = query.trim()
    if (term.length < 1 || term.length > 200) {
      setError(placesOnly ? 'Enter a school name or address.' : 'Enter a school code, name, or address.')
      return
    }
    requestRef.current?.abort()
    const controller = new AbortController()
    requestRef.current = controller
    const current = ++sequence.current
    setLoading(true)
    setError('')
    setResults(null)
    setSelected(null)
    try {
      const response = await fetch(`/api/map/places/search?q=${encodeURIComponent(term)}${placesOnly ? '&scope=places' : ''}`, { signal: controller.signal })
      const data = await response.json()
      if (current !== sequence.current) return
      if (!response.ok) throw new Error(data.error || 'Unable to search places. Please try again.')
      setResults(Array.isArray(data.results) ? data.results : [])
    } catch (failure) {
      if (current === sequence.current && failure.name !== 'AbortError') {
        setError(failure.message || 'Unable to search places. Check your connection and try again.')
      }
    } finally {
      if (current === sequence.current) setLoading(false)
    }
  }

  return (
    <div className="shrink-0 border-b bg-white p-3">
      <form onSubmit={search} role="search" aria-label="Find a school or address" className="space-y-2">
        <label htmlFor={inputId} className="block text-sm font-semibold text-slate-800">Find a school or place</label>
        <div className="flex gap-2">
          <input
            id={inputId}
            type="search"
            value={query}
            maxLength={200}
            placeholder={placesOnly ? "School name or address" : "School code (SAC), name, or address"}
            className="min-w-0 flex-1 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:outline-teal-700"
            onChange={(event) => {
              sequence.current += 1
              requestRef.current?.abort()
              setQuery(event.target.value)
              setLoading(false)
              setResults(null)
              setError('')
              setSelected(null)
            }}
          />
          <button type="submit" className="flex items-center gap-2 rounded-md bg-teal-700 px-3 py-2 text-sm font-semibold text-white hover:bg-teal-800 disabled:opacity-50" disabled={loading || query.trim().length < 1}>
            <Search className="h-4 w-4" aria-hidden="true" />
            {loading ? 'Searching…' : 'Search'}
          </button>
        </div>
      </form>
      <div aria-live="polite" className="text-sm">
        {error && <p role="alert" className="mt-2 text-red-700">{error}</p>}
        {results?.length === 0 && <p className="mt-2 text-slate-600">No matches found. Try adding the city or a street address, or place the pin on the map.</p>}
        {results?.length > 0 && (
          <ul aria-label="Place search results" className="mt-2 max-h-44 space-y-1 overflow-y-auto">
            {results.map((place, index) => (
              <li key={place.id || `${place.place_id}:${place.latitude}:${place.longitude}`}>
                <button
                  type="button"
                  className={`flex w-full gap-2 rounded-md border px-3 py-2 text-left hover:bg-teal-50 ${selected === index ? 'border-teal-600 bg-teal-50' : 'border-slate-200'}`}
                  aria-pressed={selected === index}
                  onClick={() => { setSelected(index); onChoose(place) }}
                >
                  <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-teal-700" aria-hidden="true" />
                  <span className="min-w-0"><span className="block font-semibold text-slate-900">{place.code ? `${place.code} · ` : ''}{place.name}</span><span className="block text-xs text-slate-600">{place.address || (place.school_id ? 'Listed in Others · No map location' : '')}</span></span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <p className="mt-2 text-[11px] text-slate-500">
        Places by <a className="underline" href="https://photon.komoot.io/" target="_blank" rel="noreferrer">Photon</a> · © <a className="underline" href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap contributors</a>
      </p>
    </div>
  )
}
