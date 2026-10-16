import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button.jsx'
import LegacyHouseEstimates, { HouseEstimateDetails as LegacyDetails } from './LegacyHouseEstimates.jsx'

const model = 'conditional_clean_percentage_hypergeometric'
const number = (value) => new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(value)
const percentage = (value) => `${value.toFixed(3)}%`
const interval = (values) => values.map(percentage).join(' to ')
const probability = (value) => value > 0 && value * 100 < .001 ? '<0.001%' : percentage(value * 100)

export function HouseEstimateDetails({ estimation, sessionId }) {
  if (estimation?.model !== model) return <LegacyDetails estimation={estimation} />
  if (!estimation.available) return null
  return <div className="space-y-3 text-sm text-gray-600">
    <p>Saved roster: {estimation.roster_filename || 'Student roster'} • {number(estimation.population)} eligible students in Grades 9–12.</p>
    {estimation.roster_assignment === 'manual' && <p>This session uses the existing manual roster override.</p>}
    {estimation.grade_source === 'manual_override_student_profiles' && <p>This older override has no saved grades; eligibility uses the linked student profiles.</p>}
    {!!estimation.excluded_roster_student_count && <p>{number(estimation.excluded_roster_student_count)} excluded students are removed from this session’s calculation population.</p>}
    <p>Recorded student plates: {number(estimation.student_plate_count)} • Assumed lunch absences: {number(estimation.school_absent_count)}.</p>
    <p>Known houses keep their observed plates. Anonymous CLEAN, DIRTY, and RED plates are allocated jointly among remaining students, preserving each category’s school-wide total and each house’s capacity.</p>
    <p>The predicted percentage is the expected fraction of CLEAN plates among participants, conditional on at least one participant. Absences do not enter that percentage. The probability of no recorded participants is shown separately.</p>
    <p>Point estimate = E[100 × CLEAN ÷ (CLEAN + DIRTY + RED) | at least one participant]. Each feasible allocation is weighted by the number of compatible student assignments. This is the expected percentage, rather than a ratio of expected category counts. DIRTY and RED are combined only for the percentage calculation; their separate totals remain intact.</p>
    <p>Equal-tail 90% prediction intervals apply to each house individually, conditional on participation. Discrete outcomes can give more than 90% coverage. These intervals do not promise 90% coverage across all houses together.</p>
    <p>Predicted percentages rounded to three decimals determine ties. Tied houses share a competition rank and appear alphabetically. An estimated tie can still have an uncertain actual order.</p>
    <p>Rank confidence ranges use wider percentage intervals with at least 90% simultaneous model coverage across participating houses. A range applies when that house participates and describes its possible rank by recorded CLEAN percentage. It is not a probability that the point-estimate order is correct. Coverage is unconditional across allocations; it is not a conditional guarantee given that every house participates. Touching or overlapping intervals do not establish a clear lead. Houses that might have zero participants cannot be treated as certainly ahead. Exact outcome ties share a rank.</p>
    <p>With n potentially participating houses, the rank calculation gives each house at least 1 − 0.10/n interval coverage, rounded up to the next supported 0.1% step. A union bound gives at least 90% coverage for all participating houses together, without assuming independence. The best rank counts houses whose entire interval is strictly higher and whose participation is certain. The worst rank counts every other house whose upper endpoint exceeds this house’s lower endpoint. These bounds can be conservative because the house allocations are dependent.</p>
    <p>The model assumes anonymous plate outcomes and absences are exchangeable across houses. Intervals do not account for systematic differences in house attendance, plate behavior, or recording errors. During counting, students without records are treated as assumed lunch absences; further records can change percentages, intervals, and ranks.</p>
    <p>Houses remain ordered by their predicted percentage even when confidence ranges overlap. A higher prediction does not necessarily mean a greater probability of finishing first.</p>
    {estimation.house_stats.map((house) => <div key={house.house} className="rounded-lg border bg-white p-3 space-y-2">
      <p className="font-semibold text-gray-900">{house.house} — calculation details</p>
      <p>{number(house.population)} eligible students • {number(house.total_count)} expected participants • {number(house.absent_count)} assumed absences</p>
      <p>Probability of zero recorded participants: {probability(house.zero_participation_probability)}</p>
      <p>Percentage interval used for rank confidence: {house.rank_percentage_interval ? interval(house.rank_percentage_interval) : 'Unavailable'}</p>
      {!!house.overlapping_houses?.length && <p>Overlapping rank intervals: {house.overlapping_houses.join(', ')}.</p>}
      {!!house.tied_houses?.length && <p>Same rounded point estimate: {house.tied_houses.join(', ')}.</p>}
      <div className="grid gap-2 sm:grid-cols-3">
        {[['clean', 'CLEAN'], ['dirty', 'DIRTY'], ['red', 'RED']].map(([category, label]) => <div key={category}>
          <p className="font-medium">{label}: {number(house[`${category}_count`])} expected</p>
          <p className="text-xs">{house[`observed_${category}_count`]} recorded + {number(house[`${category}_count`] - house[`observed_${category}_count`])} allocated</p>
        </div>)}
      </div>
      <p className="text-xs">Fractional counts are expectations.</p>
    </div>)}
    {estimation.house_stats.length > 0 && <SeparatingCoverage key={`${sessionId}-${estimation.calculation_signature}`} estimation={estimation} sessionId={sessionId} />}
  </div>
}

function SeparatingCoverage({ estimation, sessionId }) {
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const controller = useRef(null)
  useEffect(() => () => controller.current?.abort(), [])

  const calculate = async () => {
    if (controller.current || !sessionId) return
    const request = new AbortController()
    controller.current = request
    setBusy(true)
    setError('')
    setResult(null)
    try {
      const response = await fetch(`/api/session/${encodeURIComponent(sessionId)}/house-stats?estimate_separation=1`, { signal: request.signal })
      const data = await response.json()
      if (request.signal.aborted) return
      if (!response.ok) throw new Error(data.error || 'Unable to calculate interval separation.')
      if (data.estimation?.calculation_signature !== estimation.calculation_signature) {
        setError('The session records changed. The estimates will refresh; calculate again using the updated results.')
      } else {
        setResult(data.estimation.separating_coverage)
      }
    } catch (failure) {
      if (!request.signal.aborted) setError(failure.message || 'Unable to connect. Please try again.')
    } finally {
      if (!request.signal.aborted) {
        controller.current = null
        setBusy(false)
      }
    }
  }

  return <div className="rounded-lg border bg-gray-50 p-3 space-y-3">
    <Button type="button" variant="outline" className="h-auto max-w-full whitespace-normal text-left" disabled={busy || !sessionId} onClick={calculate}>
      {busy ? 'Calculating…' : 'Calculate highest separating coverage'}
    </Button>
    <p className="text-xs text-gray-600">Checks 0.1% to 100% coverage in 0.1 percentage-point steps. Every interval must strictly separate in the displayed ranking order; touching intervals overlap. Default intervals remain at 90%.</p>
    {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
    {result && <div role="status" className="text-sm space-y-2">
      <p className="font-medium">{result.available
        ? `Highest fully separating interval coverage: ${result.coverage_percentage.toFixed(1)}%.`
        : result.reason}</p>
      <p>The reported confidence level describes the coverage of model-based prediction intervals. It does not represent the probability that the rankings are correct or the accuracy of the predicted percentages. Lower confidence levels produce narrower intervals, making separation easier, but provide less coverage.</p>
      <p className="text-xs text-gray-600">Interval comparisons use values before display rounding. This result updates only when you calculate it; changes to the session clear it.</p>
    </div>}
  </div>
}

export default function HouseEstimates({ estimation }) {
  if (estimation?.model !== model) return <LegacyHouseEstimates estimation={estimation} />
  if (!estimation.available) return <p role="status" className="py-6 text-sm text-gray-600">{estimation.reason}</p>
  return <div className="space-y-3">
    {estimation.refresh_failed && <p role="status" className="rounded-lg bg-amber-50 p-3 text-sm text-amber-950">Unable to refresh. Showing the last available estimates; retrying automatically.</p>}
    <p className="text-sm text-gray-500">Predicted CLEAN percentages • Updates during counting. Overlapping ranges mean the order is uncertain.</p>
    {estimation.house_estimates_available === false && <p role="status" className="py-3 text-sm text-gray-600">{estimation.house_estimates_reason}</p>}
    {estimation.house_stats.map((house) => <div key={house.house} className="min-w-0 rounded-lg border bg-white p-4 shadow-sm space-y-3 [overflow-wrap:anywhere]">
      <div className="flex min-w-0 flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="font-semibold text-gray-900">{house.house}</p>
          <p className="text-sm font-medium text-teal-800">{house.percentage_rank == null ? 'Unranked • No participants possible' : `Estimated rank #${house.percentage_rank}`}</p>
        </div>
        <div className="shrink-0 text-right">
          <p className="text-2xl font-bold tabular-nums text-emerald-700">{house.clean_percentage_display == null ? '—' : `${house.clean_percentage_display}%`}</p>
          <p className="text-xs text-gray-500">Estimated clean rate</p>
        </div>
      </div>
      <div className="grid gap-2 text-sm sm:grid-cols-2">
        <div><p className="text-xs text-gray-500">90% percentage prediction interval</p><p>{house.clean_percentage_interval == null ? 'Unavailable' : interval(house.clean_percentage_interval)}</p></div>
        <div><p className="text-xs text-gray-500">90% rank confidence range</p><p>{house.rank_range ? (house.rank_range[0] === house.rank_range[1] ? `#${house.rank_range[0]}` : `#${house.rank_range[0]}–#${house.rank_range[1]}`) : 'Unranked'}</p></div>
      </div>
      {house.percentage_rank != null && <p className={`text-xs ${house.ranking_uncertain ? 'text-amber-800' : 'text-teal-800'}`}>
        {house.ranking_uncertain ? 'Order uncertain' : 'Rank resolved within the model range'}{house.tied_houses?.length ? ' • Tied point estimate' : ''}{house.zero_participation_probability > 0 ? ' • Participation uncertain' : ''}
      </p>}
    </div>)}
  </div>
}
