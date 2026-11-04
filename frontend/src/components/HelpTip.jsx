import { useEffect, useId, useRef, useState } from 'react'
import { Info, X } from 'lucide-react'
import { Label } from '@/components/ui/label.jsx'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover.jsx'
import { VIDEO_GUIDES, guideWatchUrl } from '@/lib/video-guides.js'

export function HelpTip({ topic, children, video }) {
  const [mode, setMode] = useState(null)
  const descriptionId = useId()
  const closeTimer = useRef(null)
  const panel = useRef(null)
  const activated = useRef(false)
  const guide = VIDEO_GUIDES.find(({ number }) => number === video)

  useEffect(() => () => clearTimeout(closeTimer.current), [])

  const keepOpen = () => clearTimeout(closeTimer.current)
  const showPreview = (event) => {
    if (event.pointerType !== 'mouse') return
    keepOpen()
    setMode((current) => current || 'preview')
  }
  const leavePreview = (event) => {
    if (event.pointerType !== 'mouse') return
    keepOpen()
    // Give the pointer time to cross from the icon to the help panel.
    closeTimer.current = setTimeout(() => {
      if (!panel.current?.matches(':focus-within')) {
        setMode((current) => current === 'preview' ? null : current)
      }
    }, 180)
  }

  return (
    <Popover open={mode !== null} onOpenChange={(open) => {
      keepOpen()
      setMode(open ? 'activated' : null)
    }}>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={`Help with ${topic}`}
          className="inline-flex size-6 shrink-0 cursor-help items-center justify-center rounded-full text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring"
          onPointerEnter={showPreview}
          onPointerLeave={leavePreview}
          onClick={(event) => {
            // Clicking a visible preview keeps it open for reading or following a link.
            event.preventDefault()
            keepOpen()
            activated.current = mode !== 'activated'
            setMode(activated.current ? 'activated' : null)
            if (activated.current) panel.current?.focus()
          }}
        >
          <Info size={15} aria-hidden="true" />
        </button>
      </PopoverTrigger>
      <PopoverContent
        ref={panel}
        aria-label={`Help with ${topic}`}
        aria-describedby={descriptionId}
        align="center"
        side="top"
        sideOffset={2}
        collisionPadding={12}
        className="relative z-[60] w-64 max-w-[calc(100vw-1.5rem)] p-3 text-sm leading-relaxed motion-reduce:animate-none"
        onPointerEnter={keepOpen}
        onPointerLeave={leavePreview}
        onOpenAutoFocus={(event) => {
          event.preventDefault()
          if (activated.current) panel.current?.focus()
        }}
        onCloseAutoFocus={(event) => {
          if (!activated.current) event.preventDefault()
          activated.current = false
        }}
      >
        <p id={descriptionId} className={mode === 'activated' ? 'pr-7' : undefined}>{children}</p>
        {guide && (
          <a
            className="mt-2 inline-block font-medium underline underline-offset-2"
            href={guideWatchUrl(guide)}
            target="_blank"
            rel="noopener noreferrer"
          >
            Video · {guide.title} <span aria-hidden="true">↗</span>
            <span className="sr-only"> (opens in a new tab)</span>
          </a>
        )}
        {mode === 'activated' && (
          <button
            type="button"
            aria-label="Close help"
            className="absolute right-2 top-2 inline-flex size-6 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring"
            onClick={() => setMode(null)}
          >
            <X size={14} aria-hidden="true" />
          </button>
        )}
      </PopoverContent>
    </Popover>
  )
}

export function HelpLabel({ htmlFor, label, topic = label, video, children }) {
  return (
    <div className="flex items-center gap-1">
      {htmlFor ? <Label htmlFor={htmlFor}>{label}</Label> : <span className="text-sm font-medium">{label}</span>}
      <HelpTip topic={topic} video={video}>{children}</HelpTip>
    </div>
  )
}
