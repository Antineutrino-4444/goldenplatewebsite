import React, { useEffect, useLayoutEffect } from 'react'
import { createPortal } from 'react-dom'
import { motion as Motion, useReducedMotion } from 'framer-motion'

/**
 * Modal component rendered via a React portal.
 * - Locks body scroll while open
 * - Closes on ESC key
 * - Overlay click dismissal is controlled by `dismissOnOverlayClick`
 * - Animated with framer-motion for smooth appearance
 *
 * @param {boolean} open - Whether the modal is visible
 * @param {() => void} onClose - Called when the modal requests to close
 * @param {React.ReactNode} children - Modal content
 * @param {boolean} [dismissOnOverlayClick=true] - Close when clicking the overlay
 */
export default function Modal({ open, onClose, children, dismissOnOverlayClick = true }) {
  const reduceMotion = useReducedMotion()

  // Lock before paint, and do not toggle the lock when onClose changes on a render.
  useLayoutEffect(() => {
    if (!open) return
    const originalOverflow = document.body.style.overflow
    const originalPaddingRight = document.body.style.paddingRight
    const paddingRight = parseFloat(getComputedStyle(document.body).paddingRight) || 0
    const originalWidth = document.body.clientWidth
    document.body.style.overflow = 'hidden'
    // Compensate only for width actually gained when the scrollbar disappears.
    const scrollbarWidth = document.body.clientWidth - originalWidth
    if (scrollbarWidth > 0) document.body.style.paddingRight = `${paddingRight + scrollbarWidth}px`
    return () => {
      document.body.style.overflow = originalOverflow
      document.body.style.paddingRight = originalPaddingRight
    }
  }, [open])

  useEffect(() => {
    if (!open) return

    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose?.()
    }
    document.addEventListener('keydown', handleKeyDown)

    return () => {
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open, onClose])

  if (!open) return null

  return createPortal(
    <div
      className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/50 p-4 pointer-events-auto"
      onClick={dismissOnOverlayClick ? onClose : undefined}
    >
      <Motion.div
        role="dialog"
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
        className="relative z-[2001] w-full min-w-0 max-w-sm max-h-[calc(100dvh-2rem)] overflow-x-hidden overflow-y-auto [overflow-wrap:anywhere] [&>*]:min-w-0 rounded-lg bg-white p-4 shadow-lg sm:p-6"
        initial={reduceMotion ? false : { scale: 0.98, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: 'tween', duration: reduceMotion ? 0 : 0.15, ease: 'easeOut' }}
      >
        {children}
      </Motion.div>
    </div>,
    document.body
  )
}
