import VideoHelp from '@/components/VideoHelp.jsx'
import { HelpTip } from '@/components/HelpTip.jsx'
import { useEffect, useId, useRef, useState } from 'react'
import { BarChart3, ChevronDown, RefreshCcw } from 'lucide-react'
import { Button } from '@/components/ui/button.jsx'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { compareHouses, DEFAULT_HOUSE_SCORE_SETTINGS } from '@/lib/house-ranking.js'
import HouseEstimates, { HouseEstimateDetails } from '@/components/HouseEstimates.jsx'
import MatchSessionRoster from '@/components/MatchSessionRoster.jsx'
import SessionRecordExclusions from '@/components/SessionRecordExclusions.jsx'
import { RankNumber, RankingTabs, RankingTrack } from '@/components/RankingVisuals.jsx'

const houseViews = [
  { key: 'score', label: 'Score' },
  { key: 'tickets', label: 'Tickets' },
  { key: 'estimates', label: 'Estimates' },
  { key: 'percentage', label: 'Clean Rate' },
]

function HouseStandings({ rows, view }) {
  const sorted = rows.slice().sort((a, b) => compareHouses(a, b, view))
  const tickets = view === 'tickets'
  const score = view === 'score'
  const min = score ? Math.min(0, sorted.at(-1).score) : 0
  const max = score ? Math.max(0, sorted[0].score) : tickets ? sorted[0].tickets : 100

  return (
    <ol key={view} className="space-y-2 rounded-xl border bg-gray-50 p-3 sm:p-4" aria-label="House standings">
      {sorted.map((house, index) => {
        const value = score ? house.score : tickets ? house.tickets : house.clean_rate
        const unit = score ? 'points' : tickets ? 'tickets' : `${house.clean_count} of ${house.total_count} plates clean`
        const description = tickets
          ? `${house.roster_count} ${house.roster_count === 1 ? 'student' : 'students'} on the current roster`
          : `Clean: ${house.clean_count} • Dirty: ${house.dirty_count ?? 0} • Very Dirty: ${house.red_count}`
        return (
          <li key={house.house} className={`grid min-w-0 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-2 gap-y-2 rounded-md border px-2 py-3 sm:gap-x-3 sm:px-3 ${index === 0 ? 'border-emerald-200 bg-emerald-50' : 'bg-white'}`}>
            <RankNumber rank={index + 1} />
            <div className="min-w-0">
              <p className="break-words font-semibold">{house.house}</p>
              <p className="text-xs text-muted-foreground">{description}</p>
            </div>
            <div className="max-w-36 text-right">
              <p className={`text-xl font-bold tabular-nums sm:text-2xl ${value < 0 ? 'text-red-700' : 'text-teal-800'}`}>
                {Number(value).toLocaleString()}{!score && !tickets && '%'}
              </p>
              <p className="text-xs text-muted-foreground">{unit}</p>
            </div>
            <div className="col-start-2 col-end-4">
              <RankingTrack value={value} min={min} max={max} tone={value < 0 ? 'red' : 'teal'} />
            </div>
          </li>
        )
      })}
    </ol>
  )
}

function HouseDataNotes({ children }) {
  const [open, setOpen] = useState(false)
  const contentId = useId()
  return <div className="mb-4 min-w-0 space-y-3 [overflow-wrap:anywhere]">
    <Button type="button" variant="outline" className="min-h-11 h-auto whitespace-normal" onClick={() => setOpen(!open)}
      aria-expanded={open} aria-controls={contentId}>
      {open ? 'Hide calculation details' : 'Calculation details'}
      <ChevronDown className={`h-4 w-4 transition-transform ${open ? 'rotate-180' : ''}`} />
    </Button>
    <div id={contentId} hidden={!open} className="space-y-4">{children}</div>
  </div>
}

export default function HouseRanking({ app, fillHeight = false, showVideoHelp = true }) {
  const { sessionId, houseStats, houseStatsLoading, houseSortBy, setHouseSortBy, loadHouseStats } = app
  const settings = houseStats?.score_settings || DEFAULT_HOUSE_SCORE_SETTINGS
  const ticketView = houseSortBy === 'tickets'
  const houseRows = (ticketView ? houseStats?.house_tickets : houseStats?.house_stats) ?? []
  const [reviewRequest, setReviewRequest] = useState(null)
  const [calculationRevision, setCalculationRevision] = useState(0)
  const reviewScope = reviewRequest?.sessionId === sessionId ? reviewRequest.scope : 'auto'
  const reviewVersion = reviewRequest?.sessionId === sessionId ? reviewRequest.version : 0
  const refreshReview = (scope) => setReviewRequest({ sessionId, scope, version: reviewVersion + 1 })
  const refreshEstimates = useRef(loadHouseStats)
  refreshEstimates.current = loadHouseStats
  const estimationModel = houseStats?.estimation?.model
  useEffect(() => {
    if (!sessionId || houseSortBy !== 'estimates' || estimationModel !== 'conditional_clean_percentage_hypergeometric') return
    const controller = new AbortController()
    let pending = false
    const timer = setInterval(async () => {
      if (pending || document.hidden) return
      pending = true
      try { await refreshEstimates.current({ silent: true, background: true, signal: controller.signal }) }
      finally { pending = false }
    }, 5000)
    return () => { clearInterval(timer); controller.abort() }
  }, [sessionId, houseSortBy, estimationModel])

  return (
    <Card id="house-rankings" className={`scroll-mt-4 ${fillHeight ? 'flex-1 min-h-0' : ''}`}>
      <CardHeader className="gap-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="flex flex-wrap items-center gap-2">
            <BarChart3 className="h-5 w-5 shrink-0" aria-hidden="true" />
            House Rankings
            <HelpTip topic="house ranking views">
              Score uses points and penalties. Tickets adds up current roster balances by house. Estimates models how anonymous student plates may be distributed across houses. Clean Rate ranks by the share that were clean.
            </HelpTip>
          </CardTitle>
          <Button onClick={() => loadHouseStats({ silent: false, background: Boolean(houseStats) })} variant="outline" size="sm"
            aria-label="Refresh house rankings">
            <RefreshCcw className="h-4 w-4" /> Refresh
          </Button>
        </div>
        <RankingTabs label="House ranking view" options={houseViews} value={houseSortBy} onChange={setHouseSortBy}
          className="grid-cols-2" />
      </CardHeader>
      <CardContent className={fillHeight ? 'flex-1 overflow-x-hidden overflow-y-auto' : undefined}>
        {showVideoHelp && <VideoHelp videos={[10, 11]} label="Watch: rankings and house estimates" />}
        {!sessionId ? (
          <div className="py-8 text-center text-gray-500">
            No active session selected. Switch to a session to view house data.
          </div>
        ) : houseStatsLoading ? (
          <div className="py-8 text-center text-gray-500">Loading house statistics...</div>
        ) : houseSortBy === 'estimates' ? (
          <HouseEstimates estimation={houseStats?.estimation} sessionId={sessionId} />
        ) : houseRows.length ? (
          <div className="space-y-2">
            <p className="text-xs text-muted-foreground">
              {houseSortBy === 'score' ? 'When scores cross zero, a vertical tick marks it. Negative scores extend left.'
                : ticketView ? 'Bars compare each house with the highest ticket total.'
                  : 'Bars show the share of recorded plates that were clean.'}
            </p>
            <HouseStandings rows={houseRows} view={houseSortBy} />
          </div>
        ) : ticketView ? (
          <div className="py-8 text-center text-gray-500">No houses are assigned on the current student roster.</div>
        ) : !houseStats?.has_house_data ? (
          <div className="py-8 text-center text-gray-500">
            <p className="text-lg font-medium">No House Data Available</p>
            <p className="text-sm mt-2">
              {houseStats?.message || 'The student database does not contain house information.'}
            </p>
          </div>
        ) : (
          <div className="py-8 text-center text-gray-500">No house data recorded in this session yet.</div>
        )}
        <div className="mt-6 border-t pt-4">
          <HouseDataNotes key={`notes-${sessionId}-${houseSortBy}`}>
            <CardDescription>
              {houseSortBy === 'estimates'
                ? houseStats?.estimation?.model === 'conditional_clean_percentage_hypergeometric'
                  ? 'Estimated clean rates among participants, with a 90% prediction interval for each house.'
                  : `Estimated score ranges at 95% overall model coverage. Clean +${settings.clean_points} • Dirty −${settings.dirty_penalty} • Very Dirty −${settings.very_dirty_penalty}.`
                : houseSortBy === 'score'
                  ? `Clean +${settings.clean_points} • Dirty −${settings.dirty_penalty} • Very Dirty −${settings.very_dirty_penalty}. Count-only entries and records without a house earn no points.`
                : ticketView
                  ? 'House tickets are the current ticket balances of students assigned to the house on the current roster.'
                  : 'Clean rate = clean plates ÷ all recorded plates in that house.'}
            </CardDescription>
            {houseSortBy !== 'estimates' && !ticketView && <div className="space-y-2 text-sm text-gray-600">
              <p>Records with a known house: {houseStats?.total_records_with_house ?? 0}.</p>
              {(houseStats?.house_stats || []).map((house) => <p key={house.house}>{house.house}: {house.total_count} plates • {house.percentage}% of house-attributed records • {house.clean_rate}% clean.</p>)}
            </div>}
            {houseSortBy === 'estimates' && <HouseEstimateDetails estimation={houseStats?.estimation} sessionId={sessionId} />}
          </HouseDataNotes>
          {sessionId && app.user?.role === 'superadmin' && <SessionRecordExclusions key={`records-${sessionId}`} sessionId={sessionId}
            rosterScope={reviewScope} reviewVersion={reviewVersion} onRosterScopeChange={refreshReview}
            onChanged={async () => {
              setCalculationRevision((value) => value + 1)
              await app.refreshSessionStatus(); await app.loadSessions()
            }} />}
          {sessionId && houseSortBy === 'estimates' && ['admin', 'superadmin'].includes(app.user?.role) && (
            <MatchSessionRoster key={`roster-${sessionId}`} sessionId={sessionId} loading={houseStatsLoading}
              calculationRevision={calculationRevision} onMatchFailed={() => refreshReview('current')}
              onMatched={async () => { refreshReview('auto'); await loadHouseStats({ silent: false }) }} />
          )}
        </div>
      </CardContent>
    </Card>
  )
}
