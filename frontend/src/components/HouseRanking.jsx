import { Home, RefreshCcw } from 'lucide-react'
import { Button } from '@/components/ui/button.jsx'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { compareHouses, DEFAULT_HOUSE_SCORE_SETTINGS } from '@/lib/house-ranking.js'
import HouseEstimates from '@/components/HouseEstimates.jsx'

export default function HouseRanking({ app, fillHeight = false }) {
  const { sessionId, houseStats, houseStatsLoading, houseSortBy, setHouseSortBy, loadHouseStats } = app
  const settings = houseStats?.score_settings || DEFAULT_HOUSE_SCORE_SETTINGS

  return (
    <Card className={fillHeight ? 'flex-1 flex flex-col min-h-0' : undefined}>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="flex flex-wrap items-center gap-2">
            <Home className="h-5 w-5" />House Data
          </CardTitle>
          <div className="flex flex-wrap items-center gap-2">
            <div role="tablist" aria-label="House ranking" className="flex border rounded-lg overflow-hidden">
              {[['score', 'Score'], ['count', 'Count'], ['percentage', 'Clean Rate']].map(([value, label]) => (
                <button key={value} type="button" role="tab" aria-selected={houseSortBy === value}
                  onClick={() => setHouseSortBy(value)}
                  className={`whitespace-nowrap px-3 py-1.5 text-sm transition-colors ${houseSortBy === value
                    ? 'bg-teal-600 text-white' : 'bg-white text-gray-700 hover:bg-gray-50'}`}>
                  {label}
                </button>
              ))}
            </div>
            <Button onClick={() => loadHouseStats({ silent: false })} variant="outline" size="sm"
              aria-label="Refresh house rankings">
              <RefreshCcw className="h-4 w-4" />
            </Button>
          </div>
        </div>
        <CardDescription>
          {houseSortBy === 'score'
            ? `Score ranges at 95% overall model coverage. Clean +${settings.clean_points} • Dirty −${settings.dirty_penalty} • Very Dirty −${settings.very_dirty_penalty}.`
            : houseSortBy === 'percentage'
              ? 'Clean rate = clean plates ÷ all recorded plates in that house.'
              : 'Count = all clean, dirty, and very dirty plates recorded for each house.'}
        </CardDescription>
      </CardHeader>
      <CardContent className={fillHeight ? 'flex-1 overflow-x-hidden overflow-y-auto' : undefined}>
        {!sessionId ? (
          <div className="py-8 text-center text-gray-500">
            No active session selected. Switch to a session to view house data.
          </div>
        ) : houseStatsLoading ? (
          <div className="py-8 text-center text-gray-500">Loading house statistics...</div>
        ) : houseSortBy === 'score' ? (
          <HouseEstimates estimation={houseStats?.estimation} />
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
            <div className="text-sm text-gray-500">
              Total records with house data: <span className="font-medium">{houseStats.total_records_with_house}</span>
            </div>
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
                      <div className="text-2xl font-bold text-emerald-600">
                        {houseSortBy === 'percentage' ? `${house.clean_rate}%` : house.total_count}
                      </div>
                      <div className="text-xs text-gray-500">
                        {houseSortBy === 'percentage' ? `${house.clean_count} of ${house.total_count} plates clean`
                            : `${house.clean_rate}% clean rate`}
                      </div>
                      <div className="text-xs text-gray-500">{house.percentage}% of all records</div>
                    </div>
                  </div>
                ))}
            </div>
            {(houseStats.house_stats || []).length === 0 && (
              <div className="py-8 text-center text-gray-500">No house data recorded in this session yet.</div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
