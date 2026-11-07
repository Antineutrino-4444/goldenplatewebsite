import { useEffect, useState } from 'react'
import { ListOrdered, RefreshCcw, Search } from 'lucide-react'
import { readApiJson } from '@/lib/api-errors.js'
import { leaderboardPage, normalizeLeaderboardSearch } from '@/lib/leaderboard.js'
import { Button } from '@/components/ui/button.jsx'
import { Card, CardContent, CardDescription, CardHeader } from '@/components/ui/card.jsx'
import { HelpTip } from '@/components/HelpTip.jsx'
import { Input } from '@/components/ui/input.jsx'
import { RankNumber, RankingTabs, RankingTrack } from '@/components/RankingVisuals.jsx'

const groups = [
  { key: 'faculty', label: 'Teachers' },
  { key: 'students', label: 'Students' },
]

const views = [
  { key: 'tickets', label: 'Tickets', unit: 'tickets', singular: 'ticket', tone: 'teal' },
  { key: 'clean', label: 'Clean Plates', unit: 'clean plates', singular: 'clean plate', tone: 'emerald' },
  { key: 'red', label: 'Very Dirty Plates', unit: 'very dirty plates', singular: 'very dirty plate', tone: 'amber' },
]

const valueColors = { teal: 'text-teal-800', emerald: 'text-emerald-800', amber: 'text-amber-800' }

const formatCount = (value) => value == null ? '—' : Number(value).toLocaleString()
const formatPercent = (value) => {
  if (value == null) return '—'
  if (value > 0 && value < 0.01) return '<0.01%'
  return `${Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })}%`
}

function PersonStats({ stats, view, drawContext }) {
  const metrics = [
    ...(drawContext ? [['tickets', 'Tickets']] : []),
    ['clean', 'Clean plates'],
    ['red', 'Red plates'],
    ['wins', 'Wins'],
    ...(drawContext ? [['draw_odds', 'Win chance', formatPercent]] : []),
    ...(stats.clean_rate != null ? [['clean_rate', 'Clean rate', formatPercent]] : []),
  ]
  return (
    <dl className="grid grid-cols-2 gap-x-2 gap-y-1.5 border-t border-gray-200 pt-2 min-[400px]:grid-cols-3">
      {metrics.filter(([key]) => key !== view)
        .map(([key, label, format = formatCount]) => (
          <div key={key}>
            <dt className="text-xs text-muted-foreground">{label}</dt>
            <dd className="text-sm font-semibold tabular-nums">{format(stats[key])}</dd>
          </div>
        ))}
    </dl>
  )
}

function PersonRanking({ entry, view, max, drawContext, podium = false }) {
  const { row, rank } = entry
  const unit = row.count === 1 ? view.singular : view.unit
  const count = <span className={`font-semibold tabular-nums ${podium ? 'text-xl sm:text-2xl' : 'text-lg'} ${valueColors[view.tone]}`}>{formatCount(row.count)}</span>
  const track = <RankingTrack value={row.count} max={max} tone={view.tone} />
  const rosterId = row.student_identifier || row.faculty_identifier
  const name = <>
    <span className="block break-words">{row.display_name}</span>
    {rosterId && (
      <span className="block break-all text-xs font-normal text-muted-foreground">
        ID {rosterId}
      </span>
    )}
  </>
  const stats = <PersonStats stats={row.stats} view={view.key} drawContext={drawContext} />
  if (podium) {
    return (
      <li value={rank} className={`grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 rounded-md border px-3 py-2 sm:block sm:space-y-2 sm:px-4 sm:py-3 ${rank === 1 ? 'border-emerald-200 bg-emerald-50' : 'bg-white'}`}>
        <RankNumber rank={rank} />
        <div className="col-start-1 row-start-2 min-w-0 font-semibold text-foreground">{name}</div>
        <div className="col-start-2 row-span-2 row-start-1 text-right sm:flex sm:items-baseline sm:gap-x-2 sm:text-left">
          {count}<span className="block text-xs text-muted-foreground">{unit}</span>
        </div>
        <div className="col-span-2">{track}</div>
        <div className="col-span-2 mt-1">{stats}</div>
      </li>
    )
  }
  return (
    <li value={rank} className="grid min-w-0 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-2 gap-y-2 border-b px-1 py-2.5 last:border-b-0">
      <RankNumber rank={rank} />
      <p className="min-w-0 text-sm font-semibold">{name}</p>
      <span className="text-right">{count}<span className="block text-xs text-muted-foreground sm:inline sm:pl-1.5">{unit}</span></span>
      <div className="col-start-2 col-end-4">{track}</div>
      <div className="col-span-3">{stats}</div>
    </li>
  )
}

function RankingPagination({ label, page, pageCount, onPageChange }) {
  const [pageInput, setPageInput] = useState(null)
  const changePage = (requestedPage) => {
    setPageInput(null)
    onPageChange(requestedPage)
  }
  const submitPage = (event) => {
    event.preventDefault()
    const requestedPage = Number(pageInput ?? page)
    if (Number.isInteger(requestedPage) && requestedPage >= 1 && requestedPage <= pageCount) {
      changePage(requestedPage)
    }
  }

  return (
    <nav aria-label={`${label} ranking pages`} className="flex flex-wrap items-center justify-between gap-2 text-sm">
      <Button type="button" variant="outline" size="sm" onClick={() => changePage(page - 1)} disabled={page === 1}>Previous</Button>
      <form onSubmit={submitPage} className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-1.5 whitespace-nowrap">
          Page
          <Input type="number" min={1} max={pageCount} step={1} required value={pageInput ?? page}
            aria-label={`${label} page number`} className="h-8 w-16 px-2 tabular-nums"
            onChange={(event) => setPageInput(event.target.value)} />
          of {pageCount}
        </label>
        <Button type="submit" variant="outline" size="sm">Go</Button>
      </form>
      <Button type="button" variant="outline" size="sm" onClick={() => changePage(page + 1)} disabled={page === pageCount}>Next</Button>
    </nav>
  )
}

function RankingColumn({ group, rows, view, query, page, onPageChange, drawContext }) {
  const { label } = group
  const max = rows[0]?.count ?? 0
  const { currentPage, pageCount, matchCount, visible } = leaderboardPage(rows, query, page)

  return (
    <section className="min-w-0 space-y-3 rounded-xl border bg-gray-50 p-4" aria-label={label}>
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-lg font-semibold">{label}</h3>
        <span className="text-xs text-muted-foreground">
          {query ? `${matchCount.toLocaleString()} of ${rows.length.toLocaleString()} ranked` : `${rows.length.toLocaleString()} ranked`}
        </span>
      </div>
      {drawContext && (
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <span>{drawContext.source === 'projected' ? 'Projected odds for the next draw' :
            `Current draw estimate · ${drawContext.session_name}`}</span>
          <HelpTip topic={`${label.toLowerCase()} draw odds`}>
            {drawContext.source === 'projected'
              ? 'This estimate assumes everyone on the current roster with tickets qualifies for the next draw.'
              : 'This estimate uses current-roster ticket balances. You need a qualifying clean plate in this draw to have a chance of winning.'}
          </HelpTip>
        </div>
      )}
      {pageCount > 1 && (
        <RankingPagination label={label} page={currentPage}
          pageCount={pageCount} onPageChange={onPageChange} />
      )}
      {visible.length > 0 ? (
        <ol aria-label={`${label} rankings`} className="grid gap-2">
          {visible.map((entry) => (
            <PersonRanking key={entry.row.student_id ?? entry.row.teacher_id ?? entry.rank}
              entry={entry} view={view} max={max} drawContext={drawContext} podium={!query && entry.rank <= 3} />
          ))}
        </ol>
      ) : (
        <p className="text-sm text-muted-foreground">
          {query ? 'No ranked names match your search.' : `No ${view.unit} to rank yet.`}
        </p>
      )}
    </section>
  )
}

function Rankings({ standings, view, query, drawContext }) {
  const [pages, setPages] = useState({})
  const columns = groups.filter(({ key }) => Array.isArray(standings[key]))

  return (
    <div className={`grid min-w-0 items-start gap-4 ${columns.length > 1 ? 'sm:grid-cols-2' : ''}`}>
      {columns.map((group) => (
        <RankingColumn key={group.key} group={group} rows={standings[group.key]} view={view}
          query={query} page={pages[group.key] ?? 1} drawContext={drawContext[group.key]}
          onPageChange={(page) => setPages((previous) => ({ ...previous, [group.key]: page }))} />
      ))}
    </div>
  )
}

export default function IndividualRankings({ isGuest }) {
  const [view, setView] = useState(isGuest ? 'clean' : 'tickets')
  const [search, setSearch] = useState('')
  const [revision, setRevision] = useState(0)
  const [rankings, setRankings] = useState(null)
  const [error, setError] = useState('')
  const activeView = views.find((item) => item.key === view)

  useEffect(() => {
    const controller = new AbortController()
    async function loadRankings() {
      try {
        const response = await fetch('/api/leaderboards', { signal: controller.signal })
        const data = await readApiJson(response)
        if (!response.ok) throw new Error(data.error || 'Unable to load plate leaderboards.')
        if (!controller.signal.aborted) {
          setRankings(data)
          setError('')
        }
      } catch (failure) {
        if (!controller.signal.aborted) setError(failure.message || 'Unable to load plate leaderboards.')
      }
    }
    loadRankings()
    return () => controller.abort()
  }, [revision])

  const refresh = () => {
    setRankings(null)
    setError('')
    setRevision((value) => value + 1)
  }
  const standings = rankings?.[view]
  const query = normalizeLeaderboardSearch(search)

  return (
    <Card>
      <CardHeader className="gap-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h1 id="plate-leaderboards-title" className="flex items-center gap-2 text-lg leading-none font-semibold">
            <ListOrdered className="h-5 w-5 shrink-0" aria-hidden="true" />
            Plate Leaderboards
          </h1>
          <Button type="button" variant="outline" size="sm" onClick={refresh} disabled={!rankings && !error}>
            <RefreshCcw className="h-4 w-4" /> Refresh
          </Button>
        </div>
        <CardDescription>Standings across sessions since the latest roster upload for each group.</CardDescription>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <RankingTabs label="Individual ranking view" options={views} value={view}
            className="w-full grid-cols-3 sm:w-auto" onChange={setView} />
          {standings && (
            <div className="relative w-full sm:w-60">
              <Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
              <Input type="search" value={search} aria-label={isGuest ? 'Search ranked names' : 'Search ranked names or IDs'}
                placeholder={isGuest ? 'Search by name' : 'Search by name or ID'} className="min-h-11 pl-9"
                onChange={(event) => setSearch(event.target.value)} />
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {error && <p role="alert" className="py-6 text-sm text-red-700">{error}</p>}
        {!rankings && !error && <p role="status" className="py-6 text-sm text-muted-foreground">Loading plate leaderboards…</p>}
        {rankings && !standings && <p className="py-6 text-sm text-muted-foreground">Sign in to see school-wide ticket balances.</p>}
        {standings && <Rankings key={`${view}:${query}`} standings={standings} view={activeView} query={query}
          drawContext={rankings.draw_context} />}
      </CardContent>
    </Card>
  )
}
