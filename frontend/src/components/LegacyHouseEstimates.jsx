const number = (value) => new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(value)
const range = (values) => values.map(number).join('–')
const scoreRange = (values) => values.map(number).join(' to ')

export function HouseEstimateDetails({ estimation }) {
  if (!estimation?.available) return null
  return (
    <div className="space-y-4">
      <div className="rounded-lg bg-teal-50 p-3 text-sm text-teal-950 space-y-1">
        <p>Saved roster: {estimation.roster_filename || 'Student roster'} • {number(estimation.population)} students</p>
        {estimation.roster_assignment === 'manual' && <p>This session was manually matched to this roster.</p>}
        {!!estimation.excluded_roster_student_count && <p>{number(estimation.excluded_roster_student_count)} excluded students removed from this session’s calculation population.</p>}
        <p>{number(estimation.observed_dirty_count)} dirty plates linked to students • {number(estimation.unattributed_counts.dirty)} dirty plates to estimate</p>
        <p>Assumed school absences: {number(estimation.school_absent_count)} • Student clean rate: {estimation.student_clean_percentage == null ? 'No student plates' : `${number(estimation.student_clean_percentage)}%`}</p>
      </div>
      {!!estimation.unassigned_record_count && <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-950">
        {number(estimation.unassigned_record_count)} named student records have no house in their plate or saved roster.
        They count toward school totals but receive no house rank. Count-only entries are allocated among houses separately.
      </p>}
      {!!estimation.excluded_roster_population && <p className="text-xs text-gray-500">
        {number(estimation.excluded_roster_population)} roster students have no known house and are excluded from house allocations.
        School totals still use the full saved roster.
      </p>}
      {estimation.house_estimates_available !== false && <p className="text-sm text-gray-600">
        House estimates combine recorded plates with an allocation of anonymous student plates. The model assumes similar outcomes across houses and one plate per student at lunch. Fractional counts show expected values.
      </p>}
      {estimation.house_estimates_available !== false && <p className="text-xs text-gray-500">
        Houses are ordered by expected score. Score ranges that touch or overlap indicate an uncertain order. Score ranges have at least 95% model coverage across all houses together; dirty-plate and absence ranges each have 95% coverage.
      </p>}
      {estimation.house_stats.map((house) => <div key={house.house} className="rounded-lg border bg-white p-3 space-y-2">
        <p className="font-semibold">{house.house} — calculation details</p>
        <p className="text-xs text-gray-500">{house.population} students • {house.unknown_students} unresolved • Possible score bounds: {scoreRange(house.score_bounds)}</p>
          <div className="text-xs text-gray-600 space-y-1">
            <p>{house.clearly_ahead_of.length
              ? `Clear advantage over: ${house.clearly_ahead_of.join(', ')}`
              : 'No clear ranking advantage over another house.'}</p>
            {!!house.clearly_behind.length && <p>Clearly behind: {house.clearly_behind.join(', ')}</p>}
          </div>
          <div className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
            <div>
              <p className="font-medium">Dirty plates: {number(house.dirty_count)}</p>
              <p className="text-xs text-gray-600">{house.observed_dirty_count} recorded + {number(house.estimated_additional_dirty)} estimated</p>
              <p className="text-xs text-gray-600">95% model range: {range(house.dirty_interval)}</p>
              <p className="text-xs text-gray-500">Possible: {range(house.dirty_bounds)}</p>
            </div>
            <div>
              <p className="font-medium">Estimated absences: {number(house.absent_count)}</p>
              <p className="text-xs text-gray-600">95% model range: {range(house.absent_interval)}</p>
              <p className="text-xs text-gray-500">Possible: {range(house.absent_bounds)}</p>
            </div>
          </div>
          <p className="text-xs text-gray-500">
            Clean: {number(house.clean_count)} ({house.observed_clean_count} recorded) • Very Dirty: {number(house.red_count)} ({house.observed_red_count} recorded)
            {' '}• Estimated clean rate: {house.clean_rate == null ? 'No plates' : `${number(house.clean_rate)}%`}
          </p>
      </div>)}
    </div>
  )
}

export default function HouseEstimates({ estimation }) {
  if (!estimation?.available) {
    return <p role="status" className="py-6 text-sm text-gray-600">
      {estimation?.reason || 'Estimated scores are unavailable for this session.'}
    </p>
  }
  return (
    <div className="space-y-4">
      {estimation.house_estimates_available === false && <p role="status" className="py-3 text-sm text-gray-600">
        {estimation.house_estimates_reason}
      </p>}
      {estimation.house_stats.map((house) => (
        <div key={house.house} className="rounded-lg border bg-white p-4 space-y-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="font-semibold text-gray-900">{house.house}</p>
              <p className="text-sm font-medium text-teal-800">
                Point estimate rank #{house.point_rank}
              </p>
              <p className={`text-xs ${house.rank_range[0] === house.rank_range[1] ? 'text-teal-800' : 'text-amber-800'}`}>
                {house.rank_range[0] === house.rank_range[1]
                  ? `Clear rank: ${house.rank_range[0]}` : `Order uncertain • Range-based rank: ${range(house.rank_range)}`}
              </p>
            </div>
            <div className="text-right">
              <p className="text-sm text-gray-600">95% score range: {scoreRange(house.score_interval)}</p>
              <p className={`text-xl font-bold ${house.score < 0 ? 'text-red-600' : 'text-emerald-600'}`}>{number(house.score)} points</p>
              <p className="text-xs text-gray-500">Point estimate</p>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
