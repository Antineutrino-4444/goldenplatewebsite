import VideoHelp from '@/components/VideoHelp.jsx'
import { useEffect, useId, useRef, useState } from 'react'
import { ChevronDown, Home, RefreshCcw } from 'lucide-react'
import { Button } from '@/components/ui/button.jsx'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { compareHouses, DEFAULT_HOUSE_SCORE_SETTINGS } from '@/lib/house-ranking.js'
import HouseEstimates, { HouseEstimateDetails } from '@/components/HouseEstimates.jsx'
import MatchSessionRoster from '@/components/MatchSessionRoster.jsx'
import SessionRecordExclusions from '@/components/SessionRecordExclusions.jsx'

function HouseDataNotes({ children }) {
  const [open, setOpen] = useState(false)
  const contentId = useId()
  return <div className="mb-4 min-w-0 rounded-lg border bg-gray-50 p-3 space-y-3 [overflow-wrap:anywhere]">
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
    <Card id="house-rankings" className={`min-w-0 scroll-mt-4 ${fillHeight ? 'flex-1 flex flex-col min-h-0' : ''}`}>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="flex flex-wrap items-center gap-2">
            <Home className="h-5 w-5" />House Rankings
          </CardTitle>
          <div className="flex w-full min-w-0 items-center gap-2">
            <div role="group" aria-label="House ranking view" className="grid min-w-0 flex-1 grid-cols-2 border rounded-lg overflow-hidden sm:grid-cols-4">
              {[['estimates', 'Estimates'], ['score', 'Score'], ['count', 'Count'], ['percentage', 'Clean Rate']].map(([value, label]) => (
                <button key={value} type="button" aria-pressed={houseSortBy === value}
                  onClick={() => setHouseSortBy(value)}
                  className={`min-h-11 whitespace-nowrap px-2 py-2 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-offset-[-3px] ${houseSortBy === value
                    ? 'bg-teal-600 text-white' : 'bg-white text-gray-700 hover:bg-gray-50'}`}>
                  {label}
                </button>
              ))}
            </div>
            <Button onClick={() => loadHouseStats({ silent: false, background: Boolean(houseStats) })} variant="outline" className="h-11 w-11 shrink-0" size="sm"
              aria-label="Refresh house rankings">
              <RefreshCcw className="h-4 w-4" />
            </Button>
          </div>
        </div>
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
        ) : !houseStats?.has_house_data ? (
          <div className="py-8 text-center text-gray-500">
            <Home className="h-12 w-12 mx-auto mb-4 text-gray-300" />
            <p className="text-lg font-medium">No House Data Available</p>
            <p className="text-sm mt-2">
              {houseStats?.message || 'The student database does not contain house information.'}
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="space-y-2">
              {(houseStats.house_stats || []).slice().sort((a, b) => compareHouses(a, b, houseSortBy))
                .map((house, index) => (
                  <div key={house.house}
                    className="flex min-w-0 flex-col gap-3 rounded-lg border bg-white p-4 shadow-sm sm:flex-row sm:items-center sm:justify-between [&>div]:min-w-0 [&>div]:max-w-full [&>div:first-child]:flex-1 [&>div:last-child]:shrink-0">
                    <div className="flex items-center gap-4">
                      <div className="flex items-center justify-center w-8 h-8 rounded-full bg-teal-100 text-teal-700 font-semibold text-sm">
                        #{index + 1}
                      </div>
                      <div>
                        <div className="font-semibold text-gray-900">{house.house}</div>
                        <div className="text-sm text-gray-500">
                          Clean: {house.clean_count} • Dirty: {house.dirty_count ?? 0} • Very Dirty: {house.red_count}
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className={`text-2xl font-bold ${houseSortBy === 'score' && house.score < 0 ? 'text-red-600' : 'text-emerald-600'}`}>
                        {houseSortBy === 'score' ? house.score
                          : houseSortBy === 'percentage' ? `${house.clean_rate}%` : house.total_count}
                      </div>
                      <div className="text-xs text-gray-500">
                        {houseSortBy === 'score' ? 'points'
                          : houseSortBy === 'percentage' ? `${house.clean_count} of ${house.total_count} plates clean`
                            : `${house.clean_rate}% clean rate`}
                      </div>
                    </div>
                  </div>
                ))}
            </div>
            {(houseStats.house_stats || []).length === 0 && (
              <div className="py-8 text-center text-gray-500">No house data recorded in this session yet.</div>
            )}
          </div>
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
                : houseSortBy === 'percentage'
                  ? 'Clean rate = clean plates ÷ all recorded plates in that house.'
                  : 'Count = all clean, dirty, and very dirty plates recorded for each house.'}
            </CardDescription>
            {houseSortBy !== 'estimates' && <div className="space-y-2 text-sm text-gray-600">
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
