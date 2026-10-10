import { PartyPopper, Trophy, X } from 'lucide-react'

const colors = ['#fbbf24', '#34d399', '#fb7185', '#60a5fa', '#a78bfa', '#fef3c7']

export default function CounterCelebration({ milestone, onClose }) {
  return <div className="counter-celebration pointer-events-none fixed inset-0 z-50 overflow-hidden">
    <div className="counter-confetti" aria-hidden="true">
      {Array.from({ length: 64 }, (_, index) => <span key={index} className="counter-confetti-piece" style={{
        left: `${(index * 47) % 100}%`, backgroundColor: colors[index % colors.length],
        '--drift': `${((index * 37) % 240) - 120}px`,
        '--duration': `${3.5 + (index % 8) * 0.3}s`, '--delay': `${(index % 7) * 0.12}s`,
        width: `${6 + index % 5}px`, height: `${10 + index % 8}px`,
        borderRadius: index % 3 === 0 ? '50%' : '2px',
      }} />)}
    </div>
    <div role="status" aria-live="polite" className="counter-celebration-banner pointer-events-auto absolute left-1/2 top-5 w-[calc(100%_-_2rem)] max-w-lg -translate-x-1/2 rounded-2xl border border-amber-300 bg-amber-50 p-5 text-center shadow-xl sm:top-8 sm:p-6">
      <button type="button" onClick={onClose} aria-label="Dismiss celebration"
        className="absolute right-3 top-3 rounded-full p-1 text-amber-800 hover:bg-amber-100"><X className="h-4 w-4" /></button>
      <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-amber-200 text-amber-900">
        <Trophy className="h-7 w-7" aria-hidden="true" />
      </div>
      <p className="text-xl font-bold text-amber-950">Milestone reached!</p>
      <p className="mt-2 font-semibold text-amber-900">{milestone.toLocaleString()} clean plates. Look what we achieved together!</p>
      <p className="mt-2 flex items-center justify-center gap-2 text-sm text-amber-800"><PartyPopper className="h-4 w-4" aria-hidden="true" />Less waste. More reason to celebrate.</p>
    </div>
  </div>
}
