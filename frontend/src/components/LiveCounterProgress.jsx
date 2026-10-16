import { Check, Flag, Leaf } from 'lucide-react'
import { counterBarLayout } from '@/lib/counter-animation.js'

function UpdatedNumber({ value, updateKey, percentage = false, suffix = '' }) {
  return <span key={updateKey} className="counter-value-update inline-block whitespace-nowrap">
    {value.toLocaleString(undefined, percentage ? { minimumFractionDigits: 1, maximumFractionDigits: 1 } : undefined)}{suffix}
  </span>
}

export default function LiveCounterProgress({ range, displayedCount, displayedTotal, displayedPercentage,
  milestone, metric = 'count', fullscreen = false, context }) {
  const percentage = metric === 'percentage'
  const value = percentage ? displayedPercentage : displayedCount
  const actualValue = percentage ? range.clean_percentage : range.clean_count
  const format = (number) => `${number.toLocaleString(undefined, { maximumFractionDigits: percentage ? 1 : 0 })}${percentage ? '%' : ''}`
  const difference = (number) => number.toLocaleString(undefined, { maximumFractionDigits: percentage ? 1 : 0 })
  const target = milestone || (percentage ? 100 : range.total_records)
  const progress = target ? Math.min(100, value / target * 100) : 0
  const reached = milestone && value >= milestone
  const remaining = milestone ? Math.max(0, milestone - value) : 0
  const beyond = milestone ? Math.max(0, value - milestone) : 0
  const { scale, goalWidth, extraWidth } = counterBarLayout(value, milestone, percentage ? 100 : range.total_records)
  const tick = (number) => percentage ? Math.round(number * 10) / 10 : Math.round(number)
  const ticks = scale >= 4 ? [0, tick(scale / 4), tick(scale / 2), tick(scale * 3 / 4), scale]
    : [0, scale]
  const numberLength = percentage ? actualValue.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 }).length + 1 : format(actualValue).length
  const numberSize = `${80 / Math.max(3, numberLength)}vw`
  // Follow the animated progress, clamping the colour once the goal is reached.
  const goalHue = 215 - progress * 0.6
  const goalColours = milestone ? {
    '--counter-panel-color': `hsl(${goalHue} 60% 16%)`,
    '--counter-panel-highlight': `hsl(${goalHue} 60% 23%)`,
    '--counter-panel-shadow': `hsl(${goalHue} 60% 10%)`,
    '--counter-goal-accent': `hsl(${goalHue} 75% 80%)`,
    '--counter-goal-soft': `hsl(${goalHue} 65% 90%)`,
  } : undefined

  return <div className={fullscreen ? 'counter-fullscreen' : 'space-y-5'}>
    <section style={goalColours} data-testid="live-goal-panel"
      className={fullscreen ? 'counter-fullscreen-panel text-white' : 'counter-goal-panel overflow-hidden rounded-3xl bg-emerald-900 text-white shadow-sm'}>
      <div className={fullscreen ? 'counter-fullscreen-content' : 'p-6 sm:p-9 lg:p-11'}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 className={`flex items-center gap-2 font-medium text-emerald-100 ${fullscreen ? 'text-lg sm:text-2xl' : 'text-sm'}`}>
            <Leaf className="h-5 w-5" aria-hidden="true" />{context || 'Our clean-plate progress'}
          </h3>
          {milestone && <span style={!reached ? { backgroundColor: 'var(--counter-goal-soft)' } : undefined}
            className={`inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-semibold text-emerald-950 ${reached ? 'bg-amber-200' : ''}`}>
            {reached ? <Check className="h-4 w-4" aria-hidden="true" /> : <Flag className="h-4 w-4" aria-hidden="true" />}
            {reached ? 'Milestone reached' : 'Next milestone'}
          </span>}
        </div>
        <div className={fullscreen ? 'counter-fullscreen-values' : 'mt-8 flex flex-wrap items-end justify-between gap-x-10 gap-y-6'}>
          <div className="min-w-0">
            <p data-testid={percentage ? 'live-clean-percentage' : 'live-clean-count'}
              style={fullscreen ? { '--counter-number-size': numberSize } : undefined}
              className={`font-bold tracking-tight tabular-nums ${reached ? 'counter-goal-number text-amber-300' : 'text-white'} ${fullscreen ? 'counter-fullscreen-number' : 'break-all text-7xl sm:text-8xl lg:text-9xl'}`}>
              <UpdatedNumber value={value} updateKey={actualValue} percentage={percentage} suffix={percentage ? '%' : ''} />
            </p>
            <p className={`mt-2 text-emerald-100 ${fullscreen ? 'text-xl sm:text-3xl' : 'text-lg'}`}>{percentage ? 'of recorded plates are clean' : 'clean plates and counting'}</p>
          </div>
          <div style={milestone ? { borderColor: 'var(--counter-goal-accent)', color: 'var(--counter-goal-accent)' } : undefined}
            className={milestone ? 'rounded-2xl border bg-white/5 px-5 py-4 sm:text-right' : 'pb-1 sm:text-right'}>
            <p className="text-xs font-semibold uppercase tracking-widest text-emerald-200">{milestone ? (percentage ? 'Clean-percentage goal' : 'Clean-plate goal') : (percentage ? 'Clean-plate scale' : 'Total plates recorded')}</p>
            <p className="mt-2 text-3xl font-semibold tracking-tight tabular-nums sm:text-4xl">{format(target)}</p>
          </div>
        </div>
        <div className={fullscreen ? 'counter-fullscreen-bar' : 'mt-9'}>
          <div className="mb-3 flex flex-wrap justify-between gap-2 text-sm">
            <p className="font-medium text-emerald-100">{milestone
              ? reached ? beyond ? `${difference(beyond)}${percentage ? ' percentage points' : ''} beyond our goal!` : 'We did it together!'
                : `${difference(remaining)}${percentage ? ' percentage points' : ' more'} to reach our goal`
              : 'Clean plates out of all plates recorded'}</p>
            <p className="font-semibold tabular-nums">{target ? Math.round(value / target * 100) : 0}%{milestone ? ' of goal' : ' clean'}</p>
          </div>
          <div role="progressbar" aria-label={milestone ? (percentage ? 'Clean-percentage milestone progress' : 'Clean-plate milestone progress') : 'Clean plate share'}
            aria-valuenow={Math.round(progress)} aria-valuemin={0} aria-valuemax={100}
            aria-valuetext={beyond ? `${format(value)}${percentage ? ' clean' : ' clean plates'}, ${difference(beyond)} ${percentage ? 'percentage points' : 'plates'} beyond the ${format(milestone)} goal`
              : `${format(value)}${percentage ? ' clean' : ' clean plates'} out of ${format(target)} ${milestone ? 'goal' : percentage ? 'scale' : 'total plates'}`}
            className={`overflow-hidden rounded-full bg-black/20 p-1 ${fullscreen ? 'counter-fullscreen-track' : 'h-8 sm:h-10'}`}>
            <div className="relative h-full overflow-hidden rounded-full">
              <div className="flex h-full">
                <div data-testid="live-goal-fill" style={{ width: `${goalWidth}%`, ...(milestone ? { background: 'var(--counter-goal-accent)' } : {}) }}
                  className={`h-full shrink-0 bg-gradient-to-r from-emerald-300 to-emerald-200 ${beyond ? 'rounded-l-full' : 'rounded-full'}`} />
                {beyond > 0 && <div data-testid="live-extra-fill" style={{ width: `${extraWidth}%` }}
                  className="h-full shrink-0 rounded-r-full bg-amber-300" />}
              </div>
              {beyond > 0 && <div data-testid="live-milestone-marker" aria-hidden="true" style={{ left: `${goalWidth}%` }}
                className="absolute inset-y-0 w-1 -translate-x-1/2 border-x border-white bg-emerald-950" />}
            </div>
          </div>
          <div aria-hidden="true" className="mt-3 flex justify-between gap-1 text-xs text-emerald-200 tabular-nums sm:text-sm">
            {ticks.map((value, index) => <span key={index} className={index > 0 && index < ticks.length - 1 ? 'hidden sm:inline' : ''}>{format(value)}</span>)}
          </div>
          {beyond > 0 && <div className="mt-4 flex flex-wrap justify-between gap-2 text-sm font-medium tabular-nums">
            <p className="inline-flex items-center gap-2 text-emerald-100"><span aria-hidden="true" className="h-2.5 w-2.5 rounded-full bg-emerald-200" />Milestone: {format(milestone)}</p>
            <p className="inline-flex items-center gap-2 text-amber-200"><span aria-hidden="true" className="h-2.5 w-2.5 rounded-full bg-amber-300" />+{difference(beyond)} {percentage ? 'percentage points above goal' : 'extra clean plates'}</p>
          </div>}
        </div>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-white/10 bg-black/10 px-6 py-4 text-sm text-emerald-100 sm:px-9 lg:px-11">
        <p>{range.student_clean_count.toLocaleString()} student · {range.faculty_clean_count.toLocaleString()} faculty clean plates</p>
      </div>
    </section>

    {!fullscreen && <section className="rounded-2xl border border-slate-200 bg-white p-6 sm:p-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h3 className="text-sm font-medium text-slate-500">{percentage ? 'Clean plate count' : 'Clean plate percentage'}</h3>
          <p data-testid={percentage ? 'live-clean-count' : 'live-clean-percentage'} className="mt-2 text-4xl font-bold tracking-tight text-emerald-900 tabular-nums sm:text-5xl">
            <UpdatedNumber value={percentage ? displayedCount : displayedPercentage} updateKey={percentage ? range.clean_count : range.clean_percentage}
              percentage={!percentage} suffix={percentage ? ' plates' : '%'} />
          </p>
        </div>
        <p className="text-sm text-slate-500"><span data-testid="live-total-count" className="font-semibold text-slate-800 tabular-nums"><UpdatedNumber value={displayedTotal} updateKey={range.total_records} /></span> total plates recorded</p>
      </div>
      <div role="progressbar" aria-label="Clean plate percentage" aria-valuenow={displayedPercentage}
        aria-valuemin={0} aria-valuemax={100} className="mt-5 flex h-3 overflow-hidden rounded-full bg-amber-100">
        <div style={{ width: `${displayedPercentage}%` }} className="h-full rounded-full bg-emerald-600 motion-reduce:transition-none" />
      </div>
      <div className="mt-4 flex flex-wrap justify-between gap-3 text-sm text-slate-600">
        <p className="inline-flex items-center gap-2"><span aria-hidden="true" className="h-2.5 w-2.5 rounded-full bg-emerald-600" />{range.clean_count.toLocaleString()} clean plates</p>
        <p className="inline-flex items-center gap-2"><span aria-hidden="true" className="h-2.5 w-2.5 rounded-full bg-amber-200" />{range.dirty_count.toLocaleString()} dirty or very dirty</p>
      </div>
    </section>}
    {!fullscreen && range.total_records === 0 && <p className="text-sm text-slate-500">No plates recorded in this time range yet.</p>}
  </div>
}
