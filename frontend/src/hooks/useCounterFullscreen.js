import { useEffect, useRef, useState } from 'react'

export default function useCounterFullscreen() {
  const root = useRef(null)
  const enterButton = useRef(null)
  const exitButton = useRef(null)
  const wasFullscreen = useRef(false)
  const [fullscreen, setFullscreen] = useState(false)
  const [exitVisible, setExitVisible] = useState(false)

  useEffect(() => {
    const changed = () => setFullscreen(document.fullscreenElement === root.current)
    const escape = (event) => {
      if (event.key !== 'Escape') return
      if (document.fullscreenElement === root.current) document.exitFullscreen().catch(() => {})
      setFullscreen(false)
    }
    document.addEventListener('fullscreenchange', changed)
    document.addEventListener('keydown', escape)
    return () => {
      document.removeEventListener('fullscreenchange', changed)
      document.removeEventListener('keydown', escape)
    }
  }, [])

  useEffect(() => {
    if (fullscreen) {
      root.current?.focus()
      const previousOverflow = document.body.style.overflow
      document.body.style.overflow = 'hidden'
      wasFullscreen.current = true
      const revealAtEdge = (event) => {
        const edge = 64
        setExitVisible(event.clientX <= edge || event.clientY <= edge
          || event.clientX >= window.innerWidth - edge || event.clientY >= window.innerHeight - edge)
      }
      const hide = () => setExitVisible(false)
      window.addEventListener('pointermove', revealAtEdge, { passive: true })
      window.addEventListener('pointerdown', revealAtEdge, { passive: true })
      document.addEventListener('pointerleave', hide)
      return () => {
        document.body.style.overflow = previousOverflow
        window.removeEventListener('pointermove', revealAtEdge)
        window.removeEventListener('pointerdown', revealAtEdge)
        document.removeEventListener('pointerleave', hide)
      }
    }
    if (wasFullscreen.current) {
      enterButton.current?.focus()
      wasFullscreen.current = false
    }
  }, [fullscreen])

  const enter = async () => {
    setExitVisible(false)
    setFullscreen(true)
    try { await root.current?.requestFullscreen?.() }
    catch { /* Keep the full-window display when browser fullscreen is unavailable. */ }
  }
  const exit = async () => {
    if (document.fullscreenElement === root.current) {
      try { await document.exitFullscreen() }
      catch { /* The exit control still restores the regular page. */ }
    }
    setFullscreen(false)
  }

  return { root, enterButton, exitButton, fullscreen, exitVisible, enter, exit }
}
