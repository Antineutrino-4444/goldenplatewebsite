import { Button } from '@/components/ui/button.jsx'
import './RankingVisuals.css'

const fillColors = {
  teal: 'bg-teal-600',
  emerald: 'bg-emerald-600',
  amber: 'bg-amber-600',
  red: 'bg-red-500',
}

export function RankNumber({ rank }) {
  return (
    <span className={`min-w-9 shrink-0 text-sm font-semibold tabular-nums ${rank === 1 ? 'text-[var(--site-ink)]' : 'text-muted-foreground'}`}>
      {rank == null ? '—' : `#${rank}`}
    </span>
  )
}

export function RankingTrack({ value, min = 0, max, tone = 'teal', range }) {
  const position = (number) => max > min ? Math.max(0, Math.min(100, (number - min) / (max - min) * 100)) : 0
  const left = position(range ? range[0] : Math.min(0, value))
  const right = position(range ? range[1] : Math.max(0, value))
  return (
    <div aria-hidden="true" className="relative h-1.5 rounded-sm bg-muted">
      <div className={`ranking-track-fill absolute inset-y-0 rounded-sm ${fillColors[tone]}`}
        style={{ left: `${left}%`, width: `${right - left}%` }} />
      {min < 0 && max > 0 && (
        <span className="absolute -inset-y-0.5 w-px -translate-x-1/2 bg-foreground" style={{ left: `${position(0)}%` }} />
      )}
      {range && (
        <span className={`absolute top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-card ${fillColors[tone]}`}
          style={{ left: `${position(value)}%` }} />
      )}
    </div>
  )
}

export function RankingTabs({ label, options, value, onChange, className }) {
  return (
    <div role="group" aria-label={label} className={`grid min-w-0 flex-wrap gap-2 sm:flex ${className}`}>
      {options.map(({ key, label: optionLabel }) => (
        <Button key={key} type="button" variant={value === key ? 'default' : 'outline'}
          className="min-h-11 px-2 sm:px-4" aria-pressed={value === key} onClick={() => onChange(key)}>
          {optionLabel}
        </Button>
      ))}
    </div>
  )
}
