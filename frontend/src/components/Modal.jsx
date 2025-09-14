import React, { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { AnimatePresence, motion as Motion } from 'framer-motion'

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
  // Close on ESC and prevent background scrolling
  useEffect(() => {
    if (!open) return

    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose?.()
    }
    document.addEventListener('keydown', handleKeyDown)

    const originalOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = originalOverflow
    }
  }, [open, onClose])

  return createPortal(
    <AnimatePresence>
      {open && (
        <Motion.div
          className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/50 pointer-events-auto"
          onClick={dismissOnOverlayClick ? onClose : undefined}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <Motion.div
            role="dialog"
            aria-modal="true"
            onClick={(e) => e.stopPropagation()}
            className="relative z-[2001] max-w-sm w-full rounded-lg bg-white p-6 shadow-lg"
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.95, opacity: 0 }}
          >
            {children}
          </Motion.div>
        </Motion.div>
      )}
    </AnimatePresence>,
    document.body
  )
}
