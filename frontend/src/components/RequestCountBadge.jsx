import { cn } from '@/lib/utils.js'

export default function RequestCountBadge({ count, label = 'pending requests', className }) {
  if (!(count > 0)) return null

  return (
    <span className={cn('inline-flex h-5 min-w-5 shrink-0 items-center justify-center rounded-full bg-red-600 px-1 text-xs font-semibold leading-none text-white ring-2 ring-white', className)}>
      <span aria-hidden="true">{count}</span>
      <span className="sr-only">{count} {label}</span>
    </span>
  )
}
