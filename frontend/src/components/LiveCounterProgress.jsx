import { ArrowUpRight, Check, Flag, Leaf } from 'lucide-react'
import { counterBarLayout } from '@/lib/counter-animation.js'

function UpdatedNumber({ value, updateKey }) {
  return <span key={updateKey} className="counter-value-update inline-block">{value.toLocaleString()}</span>
}

export default function LiveCounterProgress({ range, displayedCount, displayedTotal, displayedPercentage, milestone }) {
  const target = milestone || range.total_records
  const progress = target ? Math.min(100, displayedCount / target * 100) : 0
  const reached = milestone && displayedCount >= milestone
  const remaining = milestone ? Math.max(0, milestone - displayedCount) : 0
  const beyond = milestone ? Math.max(0, displayedCount - milestone) : 0
  const { scale, goalWidth, extraWidth } = counterBarLayout(displayedCount, milestone, range.total_records)
  const ticks = scale >= 4 ? [0, Math.round(scale / 4), Math.round(scale / 2), Math.round(scale * 3 / 4), scale]
    : [0, scale]

  return <div className="space-y-5">
    <section className="overflow-hidden rounded-3xl bg-emerald-900 text-white shadow-sm">
      <div className="p-6 sm:p-9 lg:p-11">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 className="flex items-center gap-2 text-sm font-medium text-emerald-100">
            <Leaf className="h-5 w-5" aria-hidden="true" />Our clean-plate progress
          </h3>
          {milestone && <span className={`inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-semibold ${reached
            ? 'bg-amber-200 text-emerald-950' : 'bg-white/10 text-emerald-100'}`}>
            {reached ? <Check className="h-4 w-4" aria-hidden="true" /> : <Flag className="h-4 w-4" aria-hidden="true" />}
            {reached ? 'Milestone reached' : 'Next milestone'}
          </span>}
        </div>
        <div className="mt-8 flex flex-wrap items-end justify-between gap-x-10 gap-y-6">
          <div className="min-w-0">
            <p data-testid="live-clean-count" className="break-all text-7xl font-bold tracking-tight tabular-nums sm:text-8xl lg:text-9xl"><UpdatedNumber value={displayedCount} updateKey={range.clean_count} /></p>
            <p className="mt-2 text-lg text-emerald-100">clean plates and counting</p>
          </div>
          <div className="pb-1 sm:text-right">
            <p className="text-xs font-semibold uppercase tracking-widest text-emerald-200">{milestone ? 'Clean-plate goal' : 'Total plates recorded'}</p>
            <p className="mt-2 text-3xl font-semibold tracking-tight tabular-nums sm:text-4xl">{target.toLocaleString()}</p>
          </div>
        </div>
        <div className="mt-9">
          <div className="mb-3 flex flex-wrap justify-between gap-2 text-sm">
            <p className="font-medium text-emerald-100">{milestone
              ? reached ? beyond ? `${beyond.toLocaleString()} beyond our goal!` : 'We did it together!'
                : `${remaining.toLocaleString()} more to reach our goal`
              : 'Clean plates out of all plates recorded'}</p>
            <p className="font-semibold tabular-nums">{target ? Math.round(displayedCount / target * 100) : 0}%{milestone ? ' of goal' : ' clean'}</p>
          </div>
          <div role="progressbar" aria-label={milestone ? 'Clean-plate milestone progress' : 'Clean plate share'}
            aria-valuenow={Math.round(progress)} aria-valuemin={0} aria-valuemax={100}
            aria-valuetext={beyond ? `${displayedCount.toLocaleString()} clean plates, ${beyond.toLocaleString()} beyond the ${milestone.toLocaleString()} plate goal`
              : `${displayedCount.toLocaleString()} clean plates out of ${target.toLocaleString()} ${milestone ? 'goal' : 'total plates'}`}
            className="h-8 overflow-hidden rounded-full bg-black/20 p-1 sm:h-10">
            <div className="relative h-full overflow-hidden rounded-full">
              <div className="flex h-full">
                <div data-testid="live-goal-fill" style={{ width: `${goalWidth}%` }}
                  className={`h-full shrink-0 bg-gradient-to-r from-emerald-300 to-emerald-200 ${beyond ? 'rounded-l-full' : 'rounded-full'}`} />
                {beyond > 0 && <div data-testid="live-extra-fill" style={{ width: `${extraWidth}%` }}
                  className="h-full shrink-0 rounded-r-full bg-amber-300" />}
              </div>
              {beyond > 0 && <div data-testid="live-milestone-marker" aria-hidden="true" style={{ left: `${goalWidth}%` }}
                className="absolute inset-y-0 w-1 -translate-x-1/2 border-x border-white bg-emerald-950" />}
            </div>
          </div>
          <div aria-hidden="true" className="mt-3 flex justify-between gap-1 text-xs text-emerald-200 tabular-nums sm:text-sm">
            {ticks.map((value, index) => <span key={index} className={index > 0 && index < ticks.length - 1 ? 'hidden sm:inline' : ''}>{value.toLocaleString()}</span>)}
          </div>
          {beyond > 0 && <div className="mt-4 flex flex-wrap justify-between gap-2 text-sm font-medium tabular-nums">
            <p className="inline-flex items-center gap-2 text-emerald-100"><span aria-hidden="true" className="h-2.5 w-2.5 rounded-full bg-emerald-200" />Milestone: {milestone.toLocaleString()}</p>
            <p className="inline-flex items-center gap-2 text-amber-200"><span aria-hidden="true" className="h-2.5 w-2.5 rounded-full bg-amber-300" />+{beyond.toLocaleString()} extra clean plates</p>
          </div>}
        </div>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-white/10 bg-black/10 px-6 py-4 text-sm text-emerald-100 sm:px-9 lg:px-11">
        <p>{range.student_clean_count.toLocaleString()} student · {range.faculty_clean_count.toLocaleString()} faculty clean plates</p>
        <p className="inline-flex items-center gap-1.5"><ArrowUpRight className="h-4 w-4" aria-hidden="true" />Every clean plate makes a difference</p>
      </div>
    </section>

    <section className="rounded-2xl border border-slate-200 bg-white p-6 sm:p-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h3 className="text-sm font-medium text-slate-500">Clean plate percentage</h3>
          <p data-testid="live-clean-percentage" className="mt-2 text-4xl font-bold tracking-tight text-emerald-900 tabular-nums sm:text-5xl"><UpdatedNumber value={displayedPercentage} updateKey={range.clean_percentage} />%</p>
        </div>
        <p className="text-sm text-slate-500"><span data-testid="live-total-count" className="font-semibold text-slate-800 tabular-nums"><UpdatedNumber value={displayedTotal} updateKey={range.total_records} /></span> total plates recorded</p>
      </div>
      <div role="progressbar" aria-label="Clean plate percentage" aria-valuenow={range.clean_percentage}
        aria-valuemin={0} aria-valuemax={100} className="mt-5 flex h-3 overflow-hidden rounded-full bg-amber-100">
        <div style={{ width: `${displayedPercentage}%` }} className="h-full rounded-full bg-emerald-600 motion-reduce:transition-none" />
      </div>
      <div className="mt-4 flex flex-wrap justify-between gap-3 text-sm text-slate-600">
        <p className="inline-flex items-center gap-2"><span aria-hidden="true" className="h-2.5 w-2.5 rounded-full bg-emerald-600" />{range.clean_count.toLocaleString()} clean plates</p>
        <p className="inline-flex items-center gap-2"><span aria-hidden="true" className="h-2.5 w-2.5 rounded-full bg-amber-200" />{range.dirty_count.toLocaleString()} dirty or very dirty</p>
      </div>
    </section>
    {range.total_records === 0 && <p className="text-sm text-slate-500">No plates recorded in this time range yet.</p>}
  </div>
}
