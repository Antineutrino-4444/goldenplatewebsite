import { useEffect, useRef, useState } from 'react'
import { counterAnimationValue, crossedMilestone } from '@/lib/counter-animation.js'

export default function useAnimatedCounter({ target, milestone, resetKey, onMilestone }) {
  const [displayed, setDisplayed] = useState(0)
  const current = useRef(0)
  const previousConfig = useRef({ key: null, milestone: undefined })

  useEffect(() => {
    const reset = previousConfig.current.key !== resetKey || previousConfig.current.milestone !== milestone
    previousConfig.current = { key: resetKey, milestone }
    if (reset) {
      current.current = 0
      setDisplayed(0)
    }
    const from = current.current
    let frame
    let started
    const advance = (value) => {
      if (crossedMilestone(current.current, value, milestone)) onMilestone(milestone)
      current.current = value
      setDisplayed(value)
    }
    if (from === target || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      advance(target)
      return
    }
    const duration = reset ? Math.min(2800, 1400 + Math.log10(Math.max(1, Math.abs(target - from))) * 200) : 650
    const animate = (timestamp) => {
      if (started === undefined) started = timestamp
      const progress = Math.min(1, (timestamp - started) / duration)
      advance(counterAnimationValue(from, target, progress))
      if (progress < 1) frame = requestAnimationFrame(animate)
    }
    frame = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(frame)
  }, [target, milestone, resetKey, onMilestone])

  return displayed
}
